import sys
import win32gui
import subprocess
import pandas as pd
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *

class EugeneVersion(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("eugeneVersion")
        self.setGeometry(300, 300, 180, 100)

        self.label = QLabel(self)
        self.label.move(40, 30)
        self.label.setText("버전처리중입니다.")

    def get_version(self):
        hwnd = win32gui.FindWindowEx(0, 0, 0, "eugeneVersion")
        if(hwnd != 0):
            p = subprocess.Popen('C:/EugeneFN/ChampionOPENAPI/ChampionOpenAPIVersionProcess.exe /' + str(hwnd))

            while True:
                msg = win32gui.GetMessage(hwnd,0,0)
                msg = msg[1]
                if msg[1] == 7422:
                    return msg[2], msg[3]

            print("Version patch fail!!")
            sys.exit()
        else:
            print("Invaild hwnd data")
            sys.exit()

class Eugene():
    def __init__(self,
                 tr_dqueue=None,
                 real_dqueues=None,
                 tr_cond_dqueue=None,
                 real_cond_dqueue=None,
                 chejan_dqueue=None):
        super().__init__()
        self.eugene = QAxWidget("CHAMPIONCOMMAGENT.ChampionCommAgentCtrl.1")

        # queues
        self.tr_dqueue          = tr_dqueue          # tr data queue
        self.real_dqueues       = real_dqueues       # real data queue list
        self.tr_cond_dqueue     = tr_cond_dqueue
        self.real_cond_dqueue   = real_cond_dqueue
        self.chejan_dqueue      = chejan_dqueue

        self.connected          = False              # for login event
        self.received           = False              # for tr event
        self.tr_items           = None               # tr input/output items
        self.tr_data            = None               # tr output data
        self.tr_record          = None
        self.tr_remained        = False
        self.condition_loaded   = False

        self._set_signals_slots()

        self.tr_output = {}
        self.rqName = None

    def get_data(self, rqId, rqName, items):
        data_list = {}

        nCntData = self.getTranOutputRow(rqId, rqName)
        if nCntData > 0:
            arrayData = []
            for i in range(nCntData):
                getDicData = {}
                for j in range(len(items)):
                    ret = self.eugene.dynamicCall("GetTranOutputData(QString, QString, QString, int)", rqId, rqName, items[j], i)
                    getDicData[items[j]] = ret.replace(" ", "")
                arrayData.append(getDicData)
            data_list[rqName] = arrayData
        else:
            if rqName != "OutRec2":
                arrayData = []
                getDicData = {}
                for i in range(len(items)):
                    ret = self.eugene.dynamicCall("GetTranOutputData(QString, QString, QString, int)", rqId, rqName, items[i], 0)
                    getDicData[items[i]] = ret.replace(" ", "")
                arrayData.append(getDicData)
                data_list[items[i]] = arrayData

        # data to DataFrame
        df = data_list
        return df

    # OnGetTranData로 Event가 들어온 경우 호출 
    def process_event_tran_data(self, rqId, block, block_len):
        if self.tr_dqueue is not None:
            items = self.tr_output[rqId]
            rqName = self.rqName
            data = self.get_data(rqId, rqName, items)
            self.tr_dqueue.put(data)
        else:
            items = self.tr_output[rqId]
            rqName = self.rqName
            data = self.get_data(rqId, rqName, items)
            self.tr_dqueue.put(data)

    def _set_signals_slots(self):
        self.eugene.OnGetTranData.connect(self.process_event_tran_data)
        #self.eugene.OnGetFidData.connect(self.process_event_fid_data)
        #self.eugene.OnGetRealData.connect(self.process_event_real_data)
        #self.eugene.OnAgentEventHandler.connect(self.process_event_agent_data)
    #================================================================
    #                           LOGIN_API
    #================================================================

    # 유진 오픈 api 로그인
    def login(self, wparam, lparam, id, pw, certPw):
        if lparam == 1:
            ret = self.eugene.dynamicCall("CommLogin(QString, QString, QString, Qstring)", wparam, id, pw, certPw)
            if ret != 0:
                return "Login error"
        else:
            return "Version patch fail"

    #================================================================
    #                           TRAN_API
    #================================================================

    # TR 조회용 고유 ID 생성
    def getRqId(self, garbage):
        ret = self.eugene.dynamicCall("CreateRequestID()")
        return ret

    # 조회시 사용한 RqId 제거
    def releaseRqId(self, rqId):
        ret = self.eugene.dynamicCall("ReleaseRqId(int)", rqId)

    # Tran Input 값 세팅
    def setTranInputData(self, rqId, trCode, id, value):
        self.eugene.dynamicCall("SetTranInputData(int, QString, QString, QString, QString)", rqId, trCode, "InRec1", id, value)
    
    # Tran Data 요청
    def requestTranData(self, rqId, trCode, nextKey, requestCnt):
        self.eugene.dynamicCall("RequestTran(int, QString, QString, int)", rqId, trCode, nextKey, requestCnt)

    # Tran 수신 데이터 건수 구하기
    def getTranOutputRow(self, trCode, recName):
        ret = self.eugene.dynamicCall("GetTranOutputRowCnt(QString, QString)", trCode, recName)
        return ret

if not QApplication.instance():
    app = QApplication(sys.argv)

if __name__ == "__main__":
    pass