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

    em.put_real(real_cmd)
    for i in range(10):
        data = em.get_real()
        pprint(data)
    sys.exit()