
import sys
import os
from PyQt5.QtWidgets import QApplication
import pythoncom
from dotenv import load_dotenv
from .eugene import Eugene, EugeneVersion

class EugeneProxy:
    app = QApplication(sys.argv)

    def __init__(self,
                 method_cqueue, method_dqueue,
                 tr_cqueue, tr_dqueue,
                 real_cqueue, real_dqueues,
                 event_dequeue, user_id, user_pw, cert_pw):
        # method queue
        self.method_cqueue  = method_cqueue
        self.method_dqueue  = method_dqueue

        # tr queue
        self.tr_cqueue      = tr_cqueue
        self.tr_dqueue      = tr_dqueue

        # real queue
        self.real_cqueue    = real_cqueue
        self.real_dqueues   = real_dqueues

        #event queue
        self.event_dequeue   = event_dequeue

        eugeneVersion = EugeneVersion()
        eugeneVersion.show()
        wparam, lparam = eugeneVersion.get_version()
        eugeneVersion.close()

        # Eugene instance
        self.eugene = Eugene(
            tr_dqueue           = self.tr_dqueue,
            real_dqueues        = self.real_dqueues,
            event_dequeue       = self.event_dequeue,
        )

        load_dotenv()
        self.eugene.login(wparam, lparam, user_id, user_pw, cert_pw)

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
                trCode = tr_cmd.get('trCode', rqId)
                input  = tr_cmd['input']
                output = tr_cmd['output']

                for id, value in input.items():
                    self.eugene.setTranInputData(rqId, trCode, id, value)

                self.eugene.tr_output[rqId] = output
                self.eugene.requestTran(rqId, trCode, "", 20)

            # real
            if not self.real_cqueue.empty():
                real_cmd = self.real_cqueue.get()

                # parameters
                realId = real_cmd['realId']
                realKey = real_cmd['realKey']
                output = real_cmd['output']

                ret = self.eugene.setReal(realId, realKey)

                if ret == 1:
                    if realId not in self.eugene.real_output:
                        self.eugene.real_output[realId] = {}

                    self.eugene.real_output[realId][realKey] = output
                else:
                    data_list = {
                        "Error": {
                            "EventType": "RegisterReal",
                            "ErrorCode": ret
                        }
                    }
                    self.event_dequeue.put(data_list)

            pythoncom.PumpWaitingMessages()