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
        self.setGeometry(300, 300, 180, 150)

        self.label = QLabel(self)
        self.label.move(40, 30)
        self.label.setText("버전처리중입니다.")

        self.btn1 = QPushButton("확인", self)
        self.btn1.move(40, 70)
        self.btn1.clicked.connect(QCoreApplication.instance().quit)
        self.btn1.setDisabled(True)

    def get_version(self):
        hwnd = win32gui.FindWindowEx(0, 0, 0, "eugeneVersion")
        if(hwnd != 0):
            p = subprocess.Popen('C:/EugeneFN/ChampionOPENAPI/ChampionOpenAPIVersionProcess.exe /' + str(hwnd))

            while True:
                msg = win32gui.GetMessage(hwnd,0,0)
                msg = msg[1]
                if msg[1] == 7422:
                    self.label.setText("  버전처리 완료")
                    self.btn1.setEnabled(True)
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

        self.event_connect_loop = QEventLoop()

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


    # 단축코드로 풀코드 구하기
    def getExpCode(self, shCode):
        ret = self.eugene.dynamicCall("GetExpCode(QString", shCode)
        return ret

    # 종목명으로 단축코드 구하기
    def getShCodeByName(self, szName):
        ret = self.eugene.dynamicCall("GetShCodeByName(QString)", szName)
        return ret

    # 마지막 에러 메시지 가져오기
    def getLastErrorMsg(self):
        ret = self.eugene.dynamicCall("GetLastErrMsg()")
        return ret

    # OnGetTranData로 Event가 들어온 경우 호출 
    def process_event_tran_data(self, rqId, block, block_len):
        if(block_len > 29):
            nCntData = self.getTranOutputRow(rqId, "OutRec1")
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
    def process_event_real_data(self, rqId, block, block_len):
        self.event_connect_loop.exit()

    # OnAgentEventHandler로 Event가 들어온 경우 호출 
    def process_event_agent_data(self, rqId, block, block_len):
        self.event_connect_loop.exit()

if not QApplication.instance():
    app = QApplication(sys.argv)

if __name__ == "__main__":
    pass

    """
    app = QApplication(sys.argv)
    eugeneVersion = EugeneVersion()
    eugeneVersion.show()
    wparam, lparam = eugeneVersion.get_version()

    eugene = Eugene()
    state = eugene.getLoginState()
    if(state == 0):
        load_dotenv()
        eugene.login(wparam, lparam, os.getenv("USER_ID"), os.getenv("USER_PW"), os.getenv("CERT_PW"))

        shCode = eugene.getShCodeByName("삼성전자")
        expCode = eugene.getExpCode(shCode)

        rqId = eugene.getRqId()
        eugene.setTranInputData(rqId, "OTD3211Q", ["ACNO", "AC_PWD", "ITEM_COD", "CMSN_ICLN_YN"], [os.getenv("ACNO"), os.getenv("ACNO_PW"), expCode, "Y"])
        print(eugene.requestTranData(rqId, "OTD3211Q", "", 20, ["AC_NM"], ["ITEM_COD", "ITEM_NM", "BAL_Q", "SEL_ABLE_Q", "CRD_TCD", "CLN_DT", "CBAS_PCHS_UPR"]))
        sys.exit()
    app.exec_()
    """