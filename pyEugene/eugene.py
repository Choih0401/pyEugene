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

        self.real_output = {}

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

    # REAL Output Data 가져오기
    def getRealOutputData(self, rqId, items):
        data_list = {}
        for i in range(len(items)):
            ret = self.eugene.dynamicCall("GetRealOutputData(QString, QString)", rqId, items[i])
            data_list[items[i]] = ret.replace(" ", "")
        
        # data to DataFrame
        df = data_list
        return df

    # OnGetTranData로 Event가 들어온 경우 호출 
    def process_event_tran_data(self, rqId, block, block_len):
        items = self.tr_output[rqId]
        rqName = self.rqName
        data = self.get_data(rqId, rqName, items)
        self.tr_dqueue.put(data)

    # OnGetRealData로 Event가 들어온 경우 호출 
    def process_event_real_data(self, realId, realKey, block, block_len):
        if(block_len > 29):
            if realKey not in self.real_output[str(realId)]:
                realKey = self.getShCode(str(realKey))
            items = self.real_output[str(realId)][str(realKey)]
            data = self.getRealOutputData(realId, items)
            self.real_dqueues.put(data)
        
    def _set_signals_slots(self):
        self.eugene.OnGetTranData.connect(self.process_event_tran_data)
        #self.eugene.OnGetFidData.connect(self.process_event_fid_data)
        self.eugene.OnGetRealData.connect(self.process_event_real_data)
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
    
    # 유진 오픈 api 로그인 상태 반환 (0=실패, 1=성공)
    def getLoginState(self):
        ret = self.eugene.dynamicCall("GetLoginState()")
        return ret

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

    #================================================================
    #                           REAL_API
    #================================================================

    # REAL 실시간 등록
    def setReal(self, realType, realKey):
        ret = self.eugene.dynamicCall("RegisterReal(int, QString)", realType, realKey)

    #================================================================
    #                           SYSTEM_API
    #================================================================

    # 단축코드로 풀코드 구하기
    def getExpCode(self, shCode):
        ret = self.eugene.dynamicCall("GetExpCode(QString", shCode)
        return ret

    # 표준코드로 단축코드 구하기
    def getShCode(self, expCode):
        ret = self.eugene.dynamicCall("GetShCode(QString", expCode)
        return ret

    # 종목명으로 단축코드 구하기
    def getShCodeByName(self, szName):
        ret = self.eugene.dynamicCall("GetShCodeByName(QString)", szName)
        return ret


if not QApplication.instance():
    app = QApplication(sys.argv)

if __name__ == "__main__":
    pass