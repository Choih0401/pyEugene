
import sys
import os
from PyQt5.QtWidgets import QApplication
import pythoncom
from dotenv import load_dotenv
from eugene import Eugene, EugeneVersion

class EugeneProxy:
    app = QApplication(sys.argv)

    def __init__(self,
                 method_cqueue, method_dqueue,
                 tr_cqueue, tr_dqueue,
                 order_cqueue,
                 real_cqueue, real_dqueues,
                 cond_cqueue, cond_dqueue,
                 tr_cond_dqueue, real_cond_dqueue,
                 chejan_dqueue):
        # method queue
        self.method_cqueue  = method_cqueue
        self.method_dqueue  = method_dqueue

        # tr queue
        self.tr_cqueue      = tr_cqueue
        self.tr_dqueue      = tr_dqueue

        # order queue
        self.order_cqueue   = order_cqueue

        # real queue
        self.real_cqueue    = real_cqueue
        self.real_dqueues   = real_dqueues

        # condition queue
        self.cond_cqueue      = cond_cqueue         # tr/real condition command queue
        self.cond_dqueue      = cond_dqueue         # condition name list queue
        self.tr_cond_dqueue   = tr_cond_dqueue      # tr condition data queue
        self.real_cond_dqueue = real_cond_dqueue    # real condition data queue

        # chejan
        self.chejan_dqueue    = chejan_dqueue

        eugeneVersion = EugeneVersion()
        eugeneVersion.show()
        wparam, lparam = eugeneVersion.get_version()
        eugeneVersion.close()

        # Eugene instance
        self.eugene = Eugene(
            tr_dqueue           = self.tr_dqueue,
            real_dqueues        = self.real_dqueues,
            tr_cond_dqueue      = self.tr_cond_dqueue,
            real_cond_dqueue    = self.real_cond_dqueue,
            chejan_dqueue       = self.chejan_dqueue
        )

        load_dotenv()
        self.eugene.login(wparam, lparam, os.getenv("USER_ID"), os.getenv("USER_PW"), os.getenv("CERT_PW"))

        # subprocess run
        self.run()

    def run(self):
        while True:
            # method
            if not self.method_cqueue.empty():
                func_name, *params = self.method_cqueue.get()

                if hasattr(self.eugene, func_name):
                    func = getattr(self.eugene, func_name)
                    result = func(*params)
                    self.method_dqueue.put(result)

            # tr
            if not self.tr_cqueue.empty():
                tr_cmd = self.tr_cqueue.get()

                # parameters
                rqId = tr_cmd['rqId']
                rqName = tr_cmd['rqName']
                trCode = tr_cmd.get('trCode', rqId)
                input  = tr_cmd['input']
                output = tr_cmd['output']

                for id, value in input.items():
                    self.eugene.setTranInputData(rqId, trCode, id, value)

                self.eugene.tr_output[rqId] = output
                self.eugene.rqName = rqName
                self.eugene.requestTranData(rqId, trCode, "", 20)

            pythoncom.PumpWaitingMessages()