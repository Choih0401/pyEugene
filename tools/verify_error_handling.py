"""
Regression checks for bugs found on review (some independently, some by an
automated Codex review on PR #37 - see the commit messages for which):

  1. A simulated pyeugene-level TR failure must surface as 502, not a
     null-filled 200 (Pydantic silently drops the unrecognized "Error" key).
  2. RealDispatcher.subscribe() must not leak an orphaned _Subscription if
     put_real() raises.
  3. Mock's unRegisterReal must actually remove the entry (a str/int type
     mismatch used to make the comparison never match).
  4. TranSpec.is_mutating must not uppercase before checking the "U" suffix
     ("dnewjtu" is a lowercase, read-only query code).
  5. A slow/hanging pyeugene call must time out with a clear 502 instead of
     hanging the HTTP request forever.
  6. WebSocket auth must accept an X-API-Key header OR a post-connect
     {"api_key": ...} handshake message - never a query parameter.
"""
import asyncio
import os
import time

os.environ.setdefault("EUGENE_MOCK_MODE", "true")
os.environ.setdefault("EUGENE_API_KEY", "testkey")

from fastapi.testclient import TestClient

from eugene_api.app_factory import build_app
from eugene_api.catalog import load_real_catalog, load_tran_catalog
from eugene_api.config import settings
from eugene_api.service import RealDispatcher

import eugene_api.mock_manager as mm

AUTH = {"X-API-Key": "testkey"}
app = build_app()

with TestClient(app) as client:
    # 1. TR error surfacing
    original_request_tr = mm.FakeEugeneManager.request_tr
    mm.FakeEugeneManager.request_tr = lambda self, cmd: {"Error": "simulated dynamicCall failure"}
    r = client.post("/tran/OAC0424Q", json={"ACNO": "123", "AC_PWD": "0000"}, headers=AUTH)
    assert r.status_code == 502, r.json()
    print("OK: simulated pyeugene TR failure surfaces as 502:", r.json())
    mm.FakeEugeneManager.request_tr = original_request_tr
    r = client.post("/tran/OAC0424Q", json={"ACNO": "123", "AC_PWD": "0000"}, headers=AUTH)
    assert r.status_code == 200
    print("OK: TR calls work normally again once the manager stops erroring")

    # 4. is_mutating case sensitivity
    tran = load_tran_catalog()
    assert tran["dnewjtu"].is_mutating is False, "dnewjtu is a lowercase query code, not an order TR"
    r = client.post("/tran/dnewjtu", json={f.item: "x" for f in tran["dnewjtu"].input}, headers=AUTH)
    assert r.status_code == 200, r.text
    print("OK: dnewjtu (lowercase, query-only) is registered and callable, not misclassified as an order TR")

    # 5. call timeout
    def hanging_request_tr(self, cmd):
        time.sleep(5)
        return {}

    mm.FakeEugeneManager.request_tr = hanging_request_tr
    original_timeout = settings.call_timeout_seconds
    object.__setattr__(settings, "call_timeout_seconds", 1.0)  # Settings is a frozen dataclass
    t0 = time.time()
    r = client.post("/tran/OAC0424Q", json={"ACNO": "1", "AC_PWD": "0"}, headers=AUTH)
    elapsed = time.time() - t0
    assert r.status_code == 502, r.json()
    assert elapsed < 3, f"expected the call to time out around 1s, took {elapsed:.1f}s"
    print(f"OK: a hanging pyeugene call times out after ~{elapsed:.1f}s instead of hanging forever:", r.json())
    object.__setattr__(settings, "call_timeout_seconds", original_timeout)
    mm.FakeEugeneManager.request_tr = original_request_tr

    # 6. WebSocket auth: header, handshake message, and rejection - never a query param
    with client.websocket_connect("/ws/real/S01?key=005930", headers=AUTH) as ws:
        assert ws.receive_json() is not None
    print("OK: WS auth via X-API-Key header works")

    with client.websocket_connect("/ws/real/S01?key=005930") as ws:
        ws.send_json({"api_key": "testkey"})
        assert ws.receive_json() is not None
    print("OK: WS auth via post-connect {'api_key': ...} handshake works (for browser clients)")

    try:
        with client.websocket_connect("/ws/real/S01?key=005930") as ws:
            ws.send_json({"api_key": "wrong"})
            ws.receive_json()
        raised = False
    except Exception:
        raised = True
    assert raised, "expected a wrong/missing API key to close the WebSocket"
    print("OK: WS rejects a missing/wrong API key")


# 2. subscribe() leak on put_real() failure
async def test_subscribe_leak():
    class BoomManager:
        def put_real(self, cmd):
            raise RuntimeError("boom")

    real_catalog = load_real_catalog()
    spec = next(iter(real_catalog.values()))
    dispatcher = RealDispatcher()
    dispatcher._manager = BoomManager()

    try:
        await dispatcher.subscribe(spec, "005930")
        raised = False
    except RuntimeError:
        raised = True

    assert raised
    assert len(dispatcher._subs) == 0, f"expected no orphaned subscription, found {dispatcher._subs}"
    print("OK: subscribe() cleans up after a failed put_real() instead of leaking")


asyncio.run(test_subscribe_leak())


# 3. mock unRegisterReal type mismatch
fake = mm.FakeEugeneManager()
fake.put_real({"realId": "21", "realKey": "005930", "output": ["SCODE"]})
assert len(fake._active_reals) == 1
fake.request_method("unRegisterReal", 21, "005930")  # int realId, like EugeneService.unregister_real() sends
assert len(fake._active_reals) == 0, f"expected unRegisterReal to remove the entry, still have {fake._active_reals}"
print("OK: mock unRegisterReal removes the entry instead of leaking it forever")

print("\nAll review-pass fix checks passed.")
