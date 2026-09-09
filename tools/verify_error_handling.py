"""Scratch verification for the 3 review-pass fixes: TR error surfacing,
subscribe() leak on put_real failure, and mock unRegisterReal type match."""
import asyncio
import os

os.environ.setdefault("EUGENE_MOCK_MODE", "true")

from fastapi.testclient import TestClient

from eugene_api.app_factory import build_app
from eugene_api.catalog import load_real_catalog
from eugene_api.service import RealDispatcher

app = build_app()

with TestClient(app) as client:
    # --- fix 1: a simulated pyeugene-level TR failure must surface as 502, not a null-filled 200 ---
    manager = app.state.__dict__  # not used; grab the live service/manager via closures instead
    from eugene_api.app_factory import build_app as _  # noqa

    # monkeypatch the manager's request_tr to simulate a pyeugene-side failure
    import eugene_api.mock_manager as mm

    original_request_tr = mm.FakeEugeneManager.request_tr

    def failing_request_tr(self, cmd):
        return {"Error": "simulated dynamicCall failure"}

    mm.FakeEugeneManager.request_tr = failing_request_tr
    r = client.post("/tran/OAC0424Q", json={"ACNO": "123", "AC_PWD": "0000"})
    print("TR error surfaces as ->", r.status_code, r.json())
    assert r.status_code == 502, "expected the simulated pyeugene error to surface as 502"
    mm.FakeEugeneManager.request_tr = original_request_tr

    r = client.post("/tran/OAC0424Q", json={"ACNO": "123", "AC_PWD": "0000"})
    print("TR back to normal ->", r.status_code)
    assert r.status_code == 200


# --- fix 2: subscribe() must not leak an orphaned _Subscription if put_real() raises ---
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


# --- fix 3: mock unRegisterReal must actually remove the entry (str/int mismatch) ---
fake = mm.FakeEugeneManager()
fake.put_real({"realId": "21", "realKey": "005930", "output": ["SCODE"]})
assert len(fake._active_reals) == 1
fake.request_method("unRegisterReal", 21, "005930")  # int realId, like EugeneService.unregister_real() sends
assert len(fake._active_reals) == 0, f"expected unRegisterReal to remove the entry, still have {fake._active_reals}"
print("OK: mock unRegisterReal removes the entry instead of leaking it forever")

print("\nAll review-pass fix checks passed.")
