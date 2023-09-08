import sys
import os
from pprint import pprint
from dotenv import load_dotenv
from eugene_manager import EugeneManager

if __name__ == "__main__":
    em = EugeneManager()
    load_dotenv()

    real_cmd = {
        'realId': '21',
        'realKey': '005930',
        'output': ["SCODE", "SNAME", "CMARKETGB", "LTIME", "CPCHECK", "LDIFF", "LCPRICE"]
    }

    real_cmd2 = {
        'realId': '21',
        'realKey': '000660',
        'output': ["SCODE", "SNAME", "CMARKETGB", "LTIME", "CPCHECK", "LDIFF", "LCPRICE"]
    }

    em.put_real(real_cmd)
    em.put_real(real_cmd2)
    for i in range(10):
        data = em.get_real()
        pprint(data)
    sys.exit()