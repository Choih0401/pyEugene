"""
Async-friendly wrapper around pyeugene's EugeneManager.

EugeneManager talks to the Champion OpenAPI subprocess through plain
multiprocessing queues: you put a request on one queue and blockingly get()
the matching response off another (see pyeugene/eugene_proxy.py). Two
separate put()/get() calls used to be able to interleave across threads and
mismatch requests with the wrong responses; EugeneManager.request_method()/
request_tr() now do each put+get pair atomically (an internal lock added in
pyeugene itself), so EugeneService just calls those directly and runs them
in a thread executor so the FastAPI event loop is never blocked.

Real-time (`real`) data is different: pyeugene delivers every registered
subscription's updates onto one shared queue. It used to carry no tag
saying which subscription an update belonged to; `Eugene.
process_event_real_data` now stamps every update with `_realId`/`_realKey`/
`_shCode` (the same realId/realKey the OnGetRealData callback already
receives from the OCX), so RealDispatcher can route each update to exactly
the subscriber(s) that asked for that (real_id, key) instead of guessing
from the update's field shape.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from eugene_api.catalog import RealSpec, TranSpec

logger = logging.getLogger("eugene_api")

_INTERNAL_TAG_KEYS = ("_realId", "_realKey", "_shCode")


class PyeugeneCallError(RuntimeError):
    """
    Raised when pyeugene itself reports a call failure.

    eugene_proxy.py's exception handling (added to stop a bug in one call
    from killing the whole subprocess) reports failures by putting
    {"Error": "..."} on the response queue instead of raising - so a failed
    call still "succeeds" as far as EugeneManager.request_tr()/
    request_method() are concerned. Without this check, that error dict was
    getting passed straight to a Pydantic response model, which silently
    drops the unknown "Error" key and returns a 200 with every field null -
    hiding the failure instead of surfacing it.
    """


class EugeneService:
    def __init__(self, manager=None):
        self._manager = manager

    def set_manager(self, manager) -> None:
        self._manager = manager

    async def _run(self, fn, *args):
        if self._manager is None:
            raise RuntimeError("EugeneService.set_manager() was not called yet (server still starting up?)")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, fn, *args)
        if isinstance(result, dict) and "Error" in result:
            raise PyeugeneCallError(str(result["Error"]))
        return result

    async def call_method(self, name: str, *params) -> Any:
        """Invokes any pyeugene Eugene method by name (e.g. getShCode, getNameByCode)."""
        return await self._run(self._manager.request_method, name, *params)

    async def call_tran(
        self,
        spec: TranSpec,
        input_values: Dict[str, str],
        next_key: str = "",
        request_cnt: int = 20,
    ) -> Dict[str, Any]:
        output_spec: Dict[str, List[str]] = {}
        if spec.output_single:
            output_spec["OutRec1"] = [f.item for f in spec.output_single]
        if spec.output_multi:
            output_spec["OutRec2"] = [f.item for f in spec.output_multi]

        rq_id = await self._run(self._manager.request_method, "getRqId", "")
        try:
            tr_cmd = {
                "rqId": rq_id,
                "trCode": spec.code,
                "input": input_values,
                "output": output_spec,
                "nextKey": next_key,
                "requestCnt": request_cnt,
            }
            return await self._run(self._manager.request_tr, tr_cmd)
        finally:
            await self._run(self._manager.request_method, "releaseRqId", rq_id)

    async def unregister_real(self, real_id: str, real_key: str) -> None:
        await self.call_method("unRegisterReal", int(real_id) if real_id.isdigit() else real_id, real_key)


@dataclass
class _Subscription:
    real_id: str
    key: str
    queue: "asyncio.Queue[dict]" = field(default_factory=asyncio.Queue)


class RealDispatcher:
    """
    Fans out pyeugene's single shared real-time queue to per-subscriber
    asyncio queues, routed by the exact (realId, realKey) each update is
    now tagged with (see module docstring).
    """

    def __init__(self):
        self._manager = None
        self._subs: List[_Subscription] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, manager, loop: asyncio.AbstractEventLoop) -> None:
        self._manager = manager
        self._loop = loop
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while True:
            try:
                data = self._manager.get_real()
            except Exception:  # pragma: no cover - defensive, keeps the dispatcher alive
                logger.exception("real-time dispatcher: get_real() failed")
                continue
            self._loop.call_soon_threadsafe(self._dispatch, data)

    def _dispatch(self, data: dict) -> None:
        real_id = data.get("_realId")
        real_key = data.get("_realKey")
        sh_code = data.get("_shCode")
        if real_id is None:
            logger.warning("real-time update had no _realId tag (old pyeugene?), dropping: %r", data)
            return

        clean = {k: v for k, v in data.items() if k not in _INTERNAL_TAG_KEYS}
        for sub in self._subs:
            if sub.real_id == real_id and sub.key in (real_key, sh_code):
                sub.queue.put_nowait(clean)

    async def subscribe(self, spec: RealSpec, key: str) -> "asyncio.Queue[dict]":
        output_fields = [f.item for f in spec.output]
        sub = _Subscription(real_id=spec.real_id, key=key)
        self._subs.append(sub)
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, self._manager.put_real, {"realId": spec.real_id, "realKey": key, "output": output_fields}
            )
        except Exception:
            # otherwise a failed put_real() leaves an orphaned subscription
            # in self._subs forever - it will never be unsubscribed, since
            # the caller never got a queue back to unsubscribe with.
            self._subs.remove(sub)
            raise
        return sub.queue

    def unsubscribe(self, spec: RealSpec, key: str, q: "asyncio.Queue[dict]") -> bool:
        """Removes one subscriber; returns True if that was the last one for (real_id, key)."""
        self._subs = [s for s in self._subs if s.queue is not q]
        return not any(s.real_id == spec.real_id and s.key == key for s in self._subs)
