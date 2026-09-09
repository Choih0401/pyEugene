"""
Exercises pyeugene bug fixes without needing Windows, PyQt5, pywin32, or a
real Champion OpenAPI account - by stubbing just enough of those modules to
import and drive the real pyeugene source directly.

Run directly (no pytest required, matches the other scripts in tests/):

    python tests/test_pyeugene_fixes.py
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
            self.login_return = 0  # override per-test to simulate CommLogin failure

        def dynamicCall(self, sig, *a):
            if sig.startswith("CommLogin"):
                return self.login_return
            return ""

    win32gui_mod = make_module(
        "win32gui",
        FindWindowEx=lambda *a, **k: 1234,
        GetMessage=lambda hwnd, a, b: (0, (0, 7422, 1, 1)),
    )
    make_module("subprocess_unused")  # placeholder, real `subprocess` module is left alone
    make_module("PyQt5")
    make_module("PyQt5.QtWidgets", QApplication=FakeQApplication, QMainWindow=FakeQMainWindow, QLabel=FakeQLabel)
    make_module("PyQt5.QtGui")
    make_module("PyQt5.QAxContainer", QAxWidget=FakeQAxWidget)
    make_module("PyQt5.QtCore")
    make_module("pythoncom", PumpWaitingMessages=lambda: None)
    return win32gui_mod


_win32gui = _install_fake_windows_stack()

from pyeugene.eugene import Eugene  # noqa: E402
from pyeugene.eugene_proxy import EugeneProxy  # noqa: E402
from pyeugene.eugene_manager import EugeneManager  # noqa: E402

# eugene.py's version-handshake path (hwnd found) shells out to a real
# Windows .exe via subprocess.Popen; replace just eugene.py's own reference
# to the subprocess module so that path is a no-op here, without touching
# the real subprocess module for the rest of the test process.
import pyeugene.eugene as _eugene_mod  # noqa: E402
_eugene_mod.subprocess = types.SimpleNamespace(Popen=lambda *a, **k: None)


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
    print("OK: real-time update tagged with", {k: v for k, v in data.items() if k.startswith("_")})


def test_release_rq_id_returns_value():
    e = Eugene(tr_dqueue=queue.Queue(), real_dqueues=queue.Queue(), event_dequeue=queue.Queue())
    e.eugene.dynamicCall = lambda *a, **k: 1
    assert e.releaseRqId(42) == 1
    print("OK: releaseRqId now returns the dynamicCall result instead of None")


def test_login_returns_zero_on_success_and_message_on_failure():
    e = Eugene(tr_dqueue=queue.Queue(), real_dqueues=queue.Queue(), event_dequeue=queue.Queue())
    e.eugene.login_return = 0
    assert e.login(1, 1, "ID", "PW", "CERT") == 0
    e.eugene.login_return = -1
    assert e.login(1, 1, "ID", "PW", "CERT") == "Login error"
    assert e.login(1, 0, "ID", "PW", "CERT") == "Version patch fail"
    print("OK: login() distinguishes success (0) from failure (message)")


class _RunOnce(Exception):
    pass


def _bare_proxy():
    proxy = object.__new__(EugeneProxy)
    proxy.method_cqueue = queue.Queue()
    proxy.method_dqueue = queue.Queue()
    proxy.tr_cqueue = queue.Queue()
    proxy.tr_dqueue = queue.Queue()
    proxy.real_cqueue = queue.Queue()
    proxy.real_dqueues = queue.Queue()
    proxy.event_dequeue = queue.Queue()
    return proxy


def test_proxy_survives_a_broken_method_call():
    """A method that raises used to kill the whole subprocess (and hang every
    caller's blocking get_*() forever); it must now just report the error and
    keep the loop going."""
    proxy = _bare_proxy()

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
        raise _RunOnce()

    import pyeugene.eugene_proxy as eugene_proxy_mod
    eugene_proxy_mod.pythoncom.PumpWaitingMessages = fake_pump

    try:
        proxy.run()
    except _RunOnce:
        pass

    result = proxy.method_dqueue.get_nowait()
    assert "Error" in result, result
    err = proxy.event_dequeue.get_nowait()
    assert err["Error"]["EventType"] == "method:crashingMethod", err
    print("OK: EugeneProxy survived a broken method call and reported it instead of hanging:", result)


def test_startup_failure_is_reported_and_raises():
    """Simulates the 'eugeneVersion window not found' case: used to be a bare
    sys.exit() with zero diagnostic; now EugeneProxy.__init__ reports it on
    event_dequeue and raises instead of dying silently."""
    _win32gui.FindWindowEx = lambda *a, **k: 0  # hwnd not found

    method_dqueue, tr_dqueue, real_dqueues, event_dequeue = queue.Queue(), queue.Queue(), queue.Queue(), queue.Queue()
    raised = False
    try:
        EugeneProxy(
            queue.Queue(), method_dqueue,
            queue.Queue(), tr_dqueue,
            queue.Queue(), real_dqueues,
            event_dequeue, "id", "pw", "certpw",
        )
    except RuntimeError:
        raised = True
    finally:
        _win32gui.FindWindowEx = lambda *a, **k: 1234  # restore for later tests

    assert raised, "expected EugeneProxy() to raise instead of exiting silently"
    err = event_dequeue.get_nowait()
    assert err["Error"]["EventType"] == "startup", err
    print("OK: startup failure reported on event_dequeue and raised instead of a silent sys.exit():", err)


def test_login_failure_is_reported_but_process_keeps_running():
    """A CommLogin failure (bad credentials) shouldn't kill the subprocess -
    it should be reported and the process should still reach run()."""
    event_dequeue = queue.Queue()
    method_cqueue, method_dqueue = queue.Queue(), queue.Queue()
    method_cqueue.put(("getLoginState", ""))  # something for run() to process once

    import pyeugene.eugene as eugene_mod
    original_ax_widget = eugene_mod.QAxWidget

    class FailingLoginAxWidget(original_ax_widget):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.login_return = -1  # CommLogin fails

    eugene_mod.QAxWidget = FailingLoginAxWidget

    calls = {"n": 0}

    def fake_pump():
        calls["n"] += 1
        raise _RunOnce()

    import pyeugene.eugene_proxy as eugene_proxy_mod
    eugene_proxy_mod.pythoncom.PumpWaitingMessages = fake_pump

    try:
        try:
            EugeneProxy(
                method_cqueue, method_dqueue,
                queue.Queue(), queue.Queue(),
                queue.Queue(), queue.Queue(),
                event_dequeue, "id", "pw", "certpw",
            )
        except _RunOnce:
            pass
    finally:
        eugene_mod.QAxWidget = original_ax_widget

    err = event_dequeue.get_nowait()
    assert err["Error"]["EventType"] == "login", err
    assert calls["n"] >= 1, "expected the process to keep going and reach run()"
    print("OK: login failure reported on event_dequeue without killing the subprocess:", err)


def test_manager_get_raises_instead_of_hanging_when_proxy_is_dead():
    """EugeneManager.get_method()/get_tr()/get_real()/getEvent() must not
    hang forever if the subprocess has died - they should raise promptly."""
    manager = object.__new__(EugeneManager)
    manager.method_dqueue = queue.Queue()  # never receives anything

    class DeadProxy:
        def is_alive(self):
            return False

    manager.proxy = DeadProxy()

    raised = False
    try:
        manager._get_or_die(manager.method_dqueue, poll_interval=0.05)
    except RuntimeError:
        raised = True
    assert raised, "expected _get_or_die() to raise instead of blocking forever"
    print("OK: EugeneManager detects a dead subprocess instead of hanging forever")


if __name__ == "__main__":
    test_get_acc_info_no_longer_crashes()
    test_real_data_is_tagged_with_subscription()
    test_release_rq_id_returns_value()
    test_login_returns_zero_on_success_and_message_on_failure()
    test_proxy_survives_a_broken_method_call()
    test_startup_failure_is_reported_and_raises()
    test_login_failure_is_reported_but_process_keeps_running()
    test_manager_get_raises_instead_of_hanging_when_proxy_is_dead()
    print("\nAll pyeugene fix checks passed.")
