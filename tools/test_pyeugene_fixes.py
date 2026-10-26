"""
Exercises the pyeugene bug fixes (getAccInfo crash, real-time subscription
tagging, EugeneProxy exception isolation) without needing Windows, PyQt5,
pywin32, or a real Champion OpenAPI account - by stubbing just enough of
those modules to import pyeugene's real source and drive it directly.
"""
import queue
import sys
import types


def _install_fake_windows_stack():
    def make_module(name, **attrs):
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod
        return mod

    class FakeSignal:
        def connect(self, *a, **k):
            pass

    class FakeQApplication:
        _instance = None

        def __init__(self, *a, **k):
            FakeQApplication._instance = self

        @classmethod
        def instance(cls):
            return cls._instance

    class FakeQMainWindow:
        def __init__(self, *a, **k):
            pass

        def setWindowTitle(self, *a, **k):
            pass

        def setGeometry(self, *a, **k):
            pass

        def show(self):
            pass

        def close(self):
            pass

    class FakeQLabel:
        def __init__(self, *a, **k):
            pass

        def move(self, *a, **k):
            pass

        def setText(self, *a, **k):
            pass

    class FakeQAxWidget:
        def __init__(self, *a, **k):
            self.OnGetTranData = FakeSignal()
            self.OnGetRealData = FakeSignal()
            self.OnAgentEventHandler = FakeSignal()

        def dynamicCall(self, *a, **k):
            return ""

    make_module("win32gui", FindWindowEx=lambda *a, **k: 0, GetMessage=lambda *a, **k: (0, (0, 0, 0, 0)))
    make_module("PyQt5")
    make_module("PyQt5.QtWidgets", QApplication=FakeQApplication, QMainWindow=FakeQMainWindow, QLabel=FakeQLabel)
    make_module("PyQt5.QtGui")
    make_module("PyQt5.QAxContainer", QAxWidget=FakeQAxWidget)
    make_module("PyQt5.QtCore")
    make_module("pythoncom", PumpWaitingMessages=lambda: None)


_install_fake_windows_stack()

from pyeugene.eugene import Eugene  # noqa: E402
from pyeugene.eugene_proxy import EugeneProxy  # noqa: E402


def test_get_acc_info_no_longer_crashes():
    e = Eugene(tr_dqueue=queue.Queue(), real_dqueues=queue.Queue(), event_dequeue=queue.Queue())
    e.eugene.dynamicCall = lambda *a, **k: "8012345678;8087654321"
    result = e.getAccInfo(None)
    assert result == ["8012345678", "8087654321"], result
    print("OK: getAccInfo no longer raises TypeError, returns", result)


def test_real_data_is_tagged_with_subscription():
    real_dqueues = queue.Queue()
    e = Eugene(tr_dqueue=queue.Queue(), real_dqueues=real_dqueues, event_dequeue=queue.Queue())
    e.eugene.dynamicCall = lambda sig, *a: "005930" if "GetShCode" in sig else "MOCK"
    e.real_output = {"21": {"000660": ["SCODE", "LCPRICE"]}}
    e.process_event_real_data(realId="21", realKey="000660", block=1, block_len=30)

    data = real_dqueues.get_nowait()
    assert data["_realId"] == "21", data
    assert data["_realKey"] == "000660", data
    assert data["_shCode"] == "005930", data
    assert data["SCODE"] == "MOCK" and data["LCPRICE"] == "MOCK"
    print("OK: real-time update tagged with", {k: v for k, v in data.items() if k.startswith("_")})


class _RunOnce(Exception):
    pass


def test_proxy_survives_a_broken_method_call():
    """A method that raises used to kill the whole subprocess (and hang every
    caller's blocking get_*() forever); it must now just report the error and
    keep the loop - and the caller must not get an error dict for tr/real
    events unrelated to the ."""
    proxy = object.__new__(EugeneProxy)
    proxy.method_cqueue = queue.Queue()
    proxy.method_dqueue = queue.Queue()
    proxy.tr_cqueue = queue.Queue()
    proxy.tr_dqueue = queue.Queue()
    proxy.real_cqueue = queue.Queue()
    proxy.real_dqueues = queue.Queue()
    proxy.event_dequeue = queue.Queue()

    class BrokenEugene:
        tr_output = {}
        real_output = {}

        def crashingMethod(self, *a):
            raise RuntimeError("boom")

    proxy.eugene = BrokenEugene()
    proxy.method_cqueue.put(("crashingMethod", "x"))

    calls = {"n": 0}

    def fake_pump():
        calls["n"] += 1
        if calls["n"] >= 1:
            raise _RunOnce()

    import pyeugene.eugene_proxy as eugene_proxy_mod
    eugene_proxy_mod.pythoncom.PumpWaitingMessages = fake_pump

    try:
        proxy.run()
    except _RunOnce:
        pass

    # the caller's get_method() must not hang forever - it gets an error payload instead
    result = proxy.method_dqueue.get_nowait()
    assert "Error" in result, result
    err = proxy.event_dequeue.get_nowait()
    assert err["Error"]["EventType"] == "method:crashingMethod", err
    print("OK: EugeneProxy survived a broken method call and reported it instead of hanging:", result)


if __name__ == "__main__":
    test_get_acc_info_no_longer_crashes()
    test_real_data_is_tagged_with_subscription()
    test_proxy_survives_a_broken_method_call()
    print("\nAll pyeugene fix checks passed.")
