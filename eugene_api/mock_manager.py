"""
A drop-in stand-in for pyeugene.eugene_manager.EugeneManager that never
touches Windows, PyQt5, or a real brokerage account.

pyeugene's real manager only runs on 32-bit Windows with the Champion
OpenAPI OCX installed and a logged-in Eugene Investment & Securities
account (see pyeugene/eugene_proxy.py). That makes it impossible to
exercise the generated REST/Swagger surface on this machine. This fake
implements the same put_*/get_* queue protocol EugeneService talks to, so
`EUGENE_MOCK_MODE=true` lets anyone explore and integration-test the API
shape without Windows or a live account.
"""
import itertools
import queue
import random
import string
import threading
import time
from typing import Any, Dict


class FakeEugeneManager:
    def __init__(self, user_id: str = "", user_pw: str = "", cert_pw: str = "", daemon: bool = True, partner_code=None):
        self._rq_id_counter = itertools.count(1)
        self._real_dqueue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._active_reals = []  # list of (realId, realKey, output_fields)
        self._stop = threading.Event()
        self._lock = threading.Lock()  # mirrors EugeneManager's request_method/request_tr locking
        self._feeder = threading.Thread(target=self._feed_real_data, daemon=daemon)
        self._feeder.start()

    # -- atomic request/response helpers (mirrors pyeugene.EugeneManager) --
    def request_method(self, name, *params):
        with self._lock:
            self.put_method((name, *params))
            return self.get_method()

    def request_tr(self, cmd):
        with self._lock:
            self.put_tr(cmd)
            return self.get_tr()

    # -- method channel -------------------------------------------------
    def put_method(self, cmd):
        name, *params = cmd
        if name == "getRqId":
            self._last_method_result = str(next(self._rq_id_counter))
        elif name == "releaseRqId":
            self._last_method_result = None
        elif name == "unRegisterReal":
            real_id, real_key = params[0], params[1]
            self._active_reals = [r for r in self._active_reals if not (r[0] == real_id and r[1] == real_key)]
            self._last_method_result = 1
        else:
            self._last_method_result = f"mock:{name}"

    def get_method(self):
        return self._last_method_result

    # -- tran channel -----------------------------------------------------
    def put_tr(self, cmd):
        self._last_tr_result = self._fake_tr_response(cmd["output"])

    def get_tr(self):
        return self._last_tr_result

    # -- real channel -----------------------------------------------------
    def put_real(self, cmd):
        self._active_reals.append((cmd["realId"], cmd["realKey"], cmd["output"]))

    def get_real(self):
        return self._real_dqueue.get()

    # -- event channel ----------------------------------------------------
    def getEvent(self):
        time.sleep(3600)
        return {}

    # -- internals ----------------------------------------------------------
    def _fake_tr_response(self, output_spec) -> Dict[str, Any]:
        result = {}
        if "OutRec1" in output_spec:
            result["OutRec1"] = {item: self._fake_value(item) for item in output_spec["OutRec1"]}
        if "OutRec2" in output_spec:
            result["OutRec2"] = [
                {item: self._fake_value(item) for item in output_spec["OutRec2"]}
                for _ in range(random.randint(1, 3))
            ]
        return result

    @staticmethod
    def _fake_value(item: str) -> str:
        if item.lower().startswith(("l", "w")) or "price" in item.lower() or item.endswith(("_A", "_Q", "_UPR")):
            return str(random.randint(0, 100000))
        return "MOCK_" + "".join(random.choices(string.ascii_uppercase, k=4))

    def _feed_real_data(self):
        while not self._stop.is_set():
            time.sleep(1)
            if not self._active_reals:
                continue
            real_id, real_key, output_fields = random.choice(self._active_reals)
            data = {item: self._fake_value(item) for item in output_fields}
            # mirrors the tagging Eugene.process_event_real_data now adds in real mode
            data["_realId"] = str(real_id)
            data["_realKey"] = str(real_key)
            data["_shCode"] = str(real_key)
            self._real_dqueue.put(data)
