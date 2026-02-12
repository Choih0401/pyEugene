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

            for i in range(100):
                msg = win32gui.GetMessage(hwnd,0,0)
                msg = msg[1]
                if msg[1] == 7422:
                    return msg[2], msg[3]
                elif i == 99:
                    return -1, -1
        else:
            print("Invaild hwnd data")
            sys.exit()

class Eugene():
    def __init__(self,
                 tr_dqueue=None,
                 real_dqueues=None,
                 event_dequeue=None):
        super().__init__()
        self.eugene = QAxWidget("CHAMPIONCOMMAGENT.ChampionCommAgentCtrl.1")

        # queues
        self.tr_dqueue          = tr_dqueue          # tr data queue
        self.real_dqueues       = real_dqueues       # real data queue list
        self.event_dequeue      = event_dequeue      # event data queue

        self._set_signals_slots()

        self.tr_output = {}
        self.real_output = {}

    # OnGetTranData로 Event가 들어온 경우 호출 
    def process_event_tran_data(self, rqId, block, block_len):
        items = self.tr_output[rqId]
        data = self.getTranOutputData(rqId, items)
        self.tr_dqueue.put(data)

    # OnGetRealData로 Event가 들어온 경우 호출 
    def process_event_real_data(self, realId, realKey, block, block_len):
        if block_len > 29:
            real_output = self.real_output.get(str(realId))
            if real_output is not None:
                items = real_output.get(str(realKey))
                if items is not None:
                    realKey = self.getShCode(str(realKey))
                    data = self.getRealOutputData(realId, items)
                    self.real_dqueues.put(data)

    # OnAgentEventHandler로 Event가 들어온 경우 호출
    def process_event_agent_data(self, eventType, nParam, strParam):
        data_list = {
            "Error": {
                "EventType": eventType,
                "nParam": nParam,
                "strParam": strParam,
            }
        }
        self.event_dequeue.put(data_list)
        
    def _set_signals_slots(self):
        self.eugene.OnGetTranData.connect(self.process_event_tran_data)
        #self.eugene.OnGetFidData.connect(self.process_event_fid_data)
        self.eugene.OnGetRealData.connect(self.process_event_real_data)
        self.eugene.OnAgentEventHandler.connect(self.process_event_agent_data)

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
    
    # 유진 오픈 api 파트너 로그인
    def loginPartner(self, wparam, lparam, id, pw, certPw, partnerCode):
        if lparam == 1:
            ret = self.eugene.dynamicCall("CommLoginPartner(QString, QString, QString, Qstring, QString)", wparam, id, pw, certPw, partnerCode)
            if ret != 0:
                return "Login error"
        else:
            return "Version patch fail"
    
    # 유진 오픈 api 로그인 상태 반환 (0=실패, 1=성공)
    def getLoginState(self, garbage):
        ret = self.eugene.dynamicCall("GetLoginState()")
        return ret

    # 로그아웃 처리 (0=실패, 1=성공)
    def logout(self, id):
        ret = self.eugene.dynamicCall("CommLogout(QString)", id)
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
    def requestTran(self, rqId, trCode, nextKey, requestCnt):
        self.eugene.dynamicCall("RequestTran(int, QString, QString, int)", rqId, trCode, nextKey, requestCnt)

    # Tran 수신 데이터 건수 구하기
    def getTranOutputRowCnt(self, trCode, recName):
        ret = self.eugene.dynamicCall("GetTranOutputRowCnt(QString, QString)", trCode, recName)
        return ret

    # TRAN Output Data 가져오기
    def getTranOutputData(self, rqId, items):
        data_list = {}

        for key in items:
            if key == "OutRec1":
                getDicData = {}
                for item in items[key]:
                    ret = self.eugene.dynamicCall("GetTranOutputData(QString, QString, QString, int)", rqId, key, item, 0)
                    getDicData[item] = ret.replace(" ", "")
                data_list[key] = getDicData
            elif key == "OutRec2":
                nCntData = self.getTranOutputRowCnt(rqId, key)
                if nCntData > 0:
                    arrayData = []
                    for i in range(nCntData):
                        getDicData = {}
                        for item in items[key]:
                            ret = self.eugene.dynamicCall("GetTranOutputData(QString, QString, QString, int)", rqId, key, item, i)
                            getDicData[item] = ret.replace(" ", "")
                        arrayData.append(getDicData)
                    data_list[key] = arrayData

        # data to DataFrame
        df = data_list
        return df

    #================================================================
    #                           REAL_API
    #================================================================

    # REAL 실시간 등록
    def setReal(self, realType, realKey):
        ret = self.eugene.dynamicCall("RegisterReal(int, QString)", realType, realKey)
        return ret

    # REAL 실시간 해제
    def unRegisterReal(self, realType, realKey):
        ret = self.eugene.dynamicCall("UnRegisterReal(int, QString)", realType, realKey)
        return ret
    
    # REAL 모든 실시간 해제
    def allUnRegisterReal(self, garbage):
        ret = self.eugene.dynamicCall("AllUnRegisterReal()")
        return ret

    # REAL Output Data 가져오기
    def getRealOutputData(self, rqId, items):
        data_list = {item: self.eugene.dynamicCall("GetRealOutputData(QString, QString)", rqId, item).replace(" ", "") for item in items}
        
        # data to DataFrame
        df = data_list
        return df

    #================================================================
    #                           FID_API
    #================================================================

    

    #================================================================
    #                           SYSTEM_API
    #================================================================

    # openApi 사용 계좌 개수 반환
    def getAccCnt(self, garbage):
        ret = self.eugene.dynamicCall("GetAccCnt()")
        return ret

    # openApi 사용 계좌번호 반환
    def getAccInfo(self, garbage):
        ret = self.eugene.dynamicCall("GetAccInfo()").split[";"]
        return ret

    # openApi 접속 모드 반환
    def getLoginMode(self, garbage):
        ret = self.eugene.dynamicCall("GetLoginMode()")
        return ret

    # 마지막 오류 메시지 변환
    def getLastErrMsg(self, garbage):
        ret = self.eugene.dynamicCall("GetLastErrMsg()")
        return ret

    # OpenAPI 파일이 위치한 경로 반환
    def getApiAgentModulePath(self, garbage):
        ret = self.eugene.dynamicCall("GetApiAgentModulePath()")
        return ret

    # 단축코드로 풀코드 구하기
    def getExpCode(self, shCode):
        ret = self.eugene.dynamicCall("GetExpCode(QString)", shCode)
        return ret

    # 표준코드로 단축코드 구하기
    def getShCode(self, expCode):
        ret = self.eugene.dynamicCall("GetShCode(QString)", expCode)
        return ret

    # 종목명으로 단축코드 구하기
    def getShCodeByName(self, szName):
        ret = self.eugene.dynamicCall("GetShCodeByName(QString)", szName)
        return ret

    # 코드로 종목명 구하기
    def getNameByCode(self, code):
        ret = self.eugene.dynamicCall("GetNameByCode(QString)", code)
        return ret
    
    # 코드로 해당 업종 구하기
    def getUpjongByCode(self, code):
        ret = self.eugene.dynamicCall("GetUpjongByCode(QString)", code)
        return ret

    # 선물 코드 구하기
    def getFutShCode(self, stype, index):
        ret = self.eugene.dynamicCall("GetFutShCode(int, int)", stype, index)
        return ret

    # 옵션 ATM 가격 구하기
    def getOptionATMPrice(self, garbage):
        ret = self.eugene.dynamicCall("GetOptionATMPrice()")
        return ret

    # 옵션 코드 구하기
    def getOptShCode(self, monthIndex, callOrPut, index):
        ret = self.eugene.dynamicCall("GetOptShCode(int, int, int)", monthIndex, callOrPut, index)
        return ret
    
    # 종목코드 시장 구분값 구하기
    def getMarketKubun(self, code):
        ret = self.eugene.dynamicCall("GetMarketKubun(QString, QString)", code, "")
        return ret

    # 해외주식 종목 정보 구하기
    def getOverseaStockInfo(self, code, itemindex):
        ret = self.eugene.dynamicCall("GetOverseaStockInfo(QString, int)", code, itemindex)
        return ret


if not QApplication.instance():
    app = QApplication(sys.argv)

if __name__ == "__main__":
    pass
