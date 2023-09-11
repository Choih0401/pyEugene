import multiprocessing as mp
from .eugene_proxy import EugeneProxy


class EugeneManager:
    def __init__(self, user_id, user_pw, cert_pw, daemon=True):
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
                user_id, user_pw, cert_pw
            ),
            daemon=daemon
        )
        self.proxy.start()

    # method
    def put_method(self, cmd):
        self.method_cqueue.put(cmd)

    def get_method(self):
        return self.method_dqueue.get()

    # tr
    def put_tr(self, cmd):
        self.tr_cqueue.put(cmd)

    def get_tr(self):
        return self.tr_dqueue.get()

    # real
    def put_real(self, cmd):
        self.real_cqueue.put(cmd)

    def get_real(self):
        return self.real_dqueues.get()

    # event
    def getEvent(self):
        return self.event_dequeue.get()