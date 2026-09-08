
import sys
import os
import traceback
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
                 event_dequeue, user_id, user_pw, cert_pw,
                 partner_code=None):
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

        # Check version patch exception
        if wparam == -1 and lparam == -1:
            print("Version patch fail!!")
            sys.exit()

        # Eugene instance
        self.eugene = Eugene(
            tr_dqueue           = self.tr_dqueue,
            real_dqueues        = self.real_dqueues,
            event_dequeue       = self.event_dequeue,
        )

        load_dotenv()
        if partner_code:
            # 제휴사 신청계좌: CommLogin이 아니라 CommLoginPartner를 호출해야 함
            self.eugene.loginPartner(wparam, lparam, user_id, user_pw, cert_pw, partner_code)
        else:
            self.eugene.login(wparam, lparam, user_id, user_pw, cert_pw)

        # subprocess run
        self.run()

    def _report_error(self, source, exc):
        traceback.print_exc()
        try:
            self.event_dequeue.put({
                "Error": {
                    "EventType": source,
                    "ErrorCode": -1,
                    "Message": f"{type(exc).__name__}: {exc}",
                }
            })
        except Exception:
            pass  # never let error reporting itself take the subprocess down

    def run(self):
        while True:
            # method
            if not self.method_cqueue.empty():
                func_name, *params = self.method_cqueue.get()
                try:
                    if hasattr(self.eugene, func_name):
                        func = getattr(self.eugene, func_name)
                        result = func(*params)
                        self.method_dqueue.put(result)
                    else:
                        self.method_dqueue.put({"Error": f"unknown method: {func_name}"})
                except Exception as exc:
                    # Without this, an exception here (e.g. a bug in the
                    # called method) used to kill the whole subprocess, and
                    # every caller blocked on get_method()/get_tr()/get_real()
                    # would then hang forever since nothing was ever put on
                    # their queue and the OS process was gone.
                    self._report_error(f"method:{func_name}", exc)
                    self.method_dqueue.put({"Error": str(exc)})

            # tr
            if not self.tr_cqueue.empty():
                tr_cmd = self.tr_cqueue.get()
                try:
                    # parameters
                    rqId = tr_cmd['rqId']
                    trCode = tr_cmd.get('trCode', rqId)
                    input  = tr_cmd['input']
                    output = tr_cmd['output']
                    # 연속조회: 호출측이 이전 응답에서 얻은 다음키/건수를 넘기지 않으면
                    # 기존과 동일하게 첫 페이지(20건)를 조회한다.
                    nextKey = tr_cmd.get('nextKey', "")
                    requestCnt = tr_cmd.get('requestCnt', 20)

                    for id, value in input.items():
                        self.eugene.setTranInputData(rqId, trCode, id, value)

                    self.eugene.tr_output[rqId] = output
                    self.eugene.requestTran(rqId, trCode, nextKey, requestCnt)
                except Exception as exc:
                    self._report_error(f"tr:{tr_cmd.get('trCode')}", exc)
                    self.tr_dqueue.put({"Error": str(exc)})

            # real
            if not self.real_cqueue.empty():
                real_cmd = self.real_cqueue.get()
                try:
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
                except Exception as exc:
                    self._report_error("real:registerReal", exc)

            pythoncom.PumpWaitingMessages()
