import threading
import multiprocessing as mp
from .eugene_proxy import EugeneProxy


class EugeneManager:
    def __init__(self, user_id, user_pw, cert_pw, daemon=True, partner_code=None):
        # SubProcess
        # method queue
        self.method_cqueue      = mp.Queue()
        self.method_dqueue      = mp.Queue()

        # tr queue
        self.tr_cqueue          = mp.Queue()
        self.tr_dqueue          = mp.Queue()

        # real queue
        self.real_cqueue        = mp.Queue()
        self.real_dqueues       = mp.Queue()

        #evnet queue
        self.event_dequeue      = mp.Queue()

        # put_x()+get_x() is two separate calls; if two threads interleave
        # them (e.g. thread A's put_tr(), then thread B's put_tr()+get_tr(),
        # then thread A's get_tr()) each thread can end up reading the
        # other's response, since there is exactly one dqueue shared by the
        # whole process. request_method()/request_tr() below do the
        # put+get pair atomically for callers that may run concurrently
        # (e.g. a web server handling multiple requests on a thread pool).
        self._request_lock = threading.Lock()

        self.proxy = mp.Process(
            target=EugeneProxy,
            args=(
                # method queue
                self.method_cqueue,
                self.method_dqueue,
                # tr queue
                self.tr_cqueue,
                self.tr_dqueue,
                # real queue
                self.real_cqueue,
                self.real_dqueues,
                # event queue
                self.event_dequeue,
                user_id, user_pw, cert_pw, partner_code,
            ),
            daemon=daemon
        )
        self.proxy.start()

    # method
    def put_method(self, cmd):
        self.method_cqueue.put(cmd)

    def get_method(self):
        return self.method_dqueue.get()

    def request_method(self, name, *params):
        """Atomic put_method()+get_method() - safe to call from multiple threads."""
        with self._request_lock:
            self.put_method((name, *params))
            return self.get_method()

    # tr
    def put_tr(self, cmd):
        self.tr_cqueue.put(cmd)

    def get_tr(self):
        return self.tr_dqueue.get()

    def request_tr(self, cmd):
        """Atomic put_tr()+get_tr() - safe to call from multiple threads."""
        with self._request_lock:
            self.put_tr(cmd)
            return self.get_tr()

    # real
    def put_real(self, cmd):
        self.real_cqueue.put(cmd)

    def get_real(self):
        return self.real_dqueues.get()

    # event
    def getEvent(self):
        return self.event_dequeue.get()
