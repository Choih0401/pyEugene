import sys
import os
import time
from pprint import pprint
from dotenv import load_dotenv
from eugene import EugeneVersion, Eugene

if __name__ == "__main__":
    eugeneVersion = EugeneVersion()
    eugeneVersion.show()
    wparam, lparam = eugeneVersion.get_version()

    eugene = Eugene()
    state = eugene.getLoginState()
    eugeneVersion.close()
    if(state == 0):
        load_dotenv()
        eugene.login(wparam, lparam, os.getenv("USER_ID"), os.getenv("USER_PW"), os.getenv("CERT_PW"))

        shCode = eugene.getShCodeByName("삼성전자")
        expCode = eugene.getExpCode(shCode)

        items = [
            "SCODE",
            "SNAME",
            "CMARKETGB",
            "LTIME",
            "CPCHECK",
            "LDIFF",
            "LCPRICE"
        ]

        eugene.setReal(5, shCode, items)
        for i in range(10):
            pprint(eugene.getReturnRealData())
        eugene.expReal(5, shCode)
        sys.exit()