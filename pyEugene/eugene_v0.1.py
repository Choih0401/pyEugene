import sys
import win32gui
import subprocess
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
    def __init__(self):
        super().__init__()
        self.eugene = QAxWidget("CHAMPIONCOMMAGENT.ChampionCommAgentCtrl.1")
        self.eugene.OnGetTranData.connect(self.process_event_tran_data)
        self.eugene.OnGetFidData.connect(self.process_event_fid_data)
        self.eugene.OnGetRealData.connect(self.process_event_real_data)
        self.eugene.OnAgentEventHandler.connect(self.process_event_agent_data)

        self.getData = []
        self.getDataArray = []
        self.returnData = {}
        self.returnRealData = {}

        self.event_connect_loop = QEventLoop()

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
    def getRqId(self):
        ret = self.eugene.dynamicCall("CreateRequestID()")
        return ret

    # 조회시 사용한 RqId 제거
    def releaseRqId(self, rqId):
        ret = self.eugene.dynamicCall("ReleaseRqId(int)", rqId)

    # Tran Input 값 세팅
    def setTranInputData(self, rqId, trCode, item, itemValue):
        for i in range(len(item)):
            ret = self.eugene.dynamicCall("SetTranInputData(int, QString, QString, QString, QString)", rqId, trCode, "InRec1", item[i], itemValue[i])
            if ret != 1:
                error = self.getLastErrorMsg()
                return error
                break
    
    # Tran Data 요청
    def requestTranData(self, rqId, trCode, nextKey, requestCnt, getData=[], getDataArray=[]):
        self.getData = getData              #OutRec1 값
        self.getDataArray = getDataArray    #OutRec2 값

        ret = self.eugene.dynamicCall("RequestTran(int, QString, QString, int)", rqId, trCode, nextKey, requestCnt)
        self.event_connect_loop.exec_()

        return self.returnData

    # Tran 수신 데이터 건수 구하기
    def getTranOutputRow(self, trCode, recName):
        ret = self.eugene.dynamicCall("GetTranOutputRowCnt(QString, QString)", trCode, recName)
        return ret

    # Tran Output Data 가져오기
    def getTranOutputData(self, trCode, recName, itemName, nCntData):
        if nCntData > 0:                   # Array Data가 있는 경우
            returnArrayData = []
            for i in range(nCntData):
                getDicData = {}
                for j in range(len(itemName)):
                    ret = self.eugene.dynamicCall("GetTranOutputData(QString, QString, QString, int)", trCode, recName, itemName[j], i)
                    getDicData[itemName[j]] = ret.replace(" ", "")
                returnArrayData.append(getDicData)
            self.returnData["OutRec2"] = returnArrayData
        else:                              # Array Data가 없는 경우
            for i in range(len(itemName)):
                ret = self.eugene.dynamicCall("GetTranOutputData(QString, QString, QString, int)", trCode, recName, itemName[i], 0)
                self.returnData[itemName[i]] = ret.replace(" ", "")

    #================================================================
    #                           REAL_API
    #================================================================

    # REAL 실시간 등록
    def setReal(self, realType, realKey, getData=[]):
        self.getData = getData              #OutRec1 값
        ret = self.eugene.dynamicCall("RegisterReal(int, QString)", realType, realKey)

    # REAL 실시간 해제
    def expReal(self, realType, realKey):
        ret = self.eugene.dynamicCall("UnRegisterReal(int, QString)", realType, realKey)
        return ret

    # 모든 REAL 실시간 해제
    def expAllReal(self):
        ret = self.eugene.dynamicCall("AllUnRegisterReal()")
        return ret

    # REAL Output Data 가져오기
    def getRealOutputData(self, realType, itemName):
        getDicData = {}
        for i in range(len(itemName)):
            ret = self.eugene.dynamicCall("GetRealOutputData(QString, QString)", realType, itemName[i])
            getDicData[itemName[i]] = ret.replace(" ", "")
        self.returnRealData[realType] = getDicData

    def getReturnRealData(self, realType=0):
        self.event_connect_loop.exec_()
        if realType == 0:
            return self.returnRealData
        else:
            return self.returnRealData[realType]

    #================================================================
    #                           SYSTEM_API
    #================================================================

    # 단축코드로 풀코드 구하기
    def getExpCode(self, shCode):
        ret = self.eugene.dynamicCall("GetExpCode(QString", shCode)
        return ret

    # 표준코드로 단축코드 구하기
    def getShCode(self, expCode):
        ret = self.eugene.dynamicCall("GetShCode(QString", 구하기)
        return ret

    # 종목명으로 단축코드 구하기
    def getShCodeByName(self, szName):
        ret = self.eugene.dynamicCall("GetShCodeByName(QString)", szName)
        return ret

    # 마지막 에러 메시지 가져오기
    def getLastErrorMsg(self):
        ret = self.eugene.dynamicCall("GetLastErrMsg()")
        return ret

    #================================================================
    #                           GET_EVENT
    #================================================================

    # OnGetTranData로 Event가 들어온 경우 호출 
    def process_event_tran_data(self, rqId, block, block_len):
        if(block_len > 29):
            nCntData = self.getRealOutputData(rqId, "OutRec1")
            if nCntData > 0:
                self.getTranOutputData(rqId, "OutRec1", self.getData, 0)

            nCntData = self.getTranOutputRow(rqId, "OutRec2")
            if nCntData > 0:
                self.getTranOutputData(rqId, "OutRec2", self.getDataArray, nCntData)


        self.releaseRqId(rqId)
        self.event_connect_loop.exit()

    # OnGetFidData로 Event가 들어온 경우 호출
    def process_event_fid_data(self, rqId, block, block_len):
        self.event_connect_loop.exit()

    # OnGetRealData로 Event가 들어온 경우 호출 
    def process_event_real_data(self, pbId, realKey, block, block_len):
        if(block_len > 29):
            self.getRealOutputData(pbId, self.getData)

        self.event_connect_loop.exit()

    # OnAgentEventHandler로 Event가 들어온 경우 호출 
    def process_event_agent_data(self, rqId, block, block_len):
        self.event_connect_loop.exit()

if not QApplication.instance():
    app = QApplication(sys.argv)

if __name__ == "__main__":
    pass