import sys
import os
from pprint import pprint
from dotenv import load_dotenv
from eugene import EugeneVersion, Eugene

if __name__ == "__main__":
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
        pprint(eugene.requestTranData(rqId, "OTD3211Q", "", 20, ["AC_NM"], ["ITEM_COD", "ITEM_NM", "BAL_Q", "SEL_ABLE_Q", "CRD_TCD", "CLN_DT", "CBAS_PCHS_UPR"]))
        sys.exit()