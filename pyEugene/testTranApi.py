import sys
import os
from pprint import pprint
from dotenv import load_dotenv
from eugene_manager import EugeneManager

if __name__ == "__main__":
    em = EugeneManager()
    load_dotenv()

    em.put_method(("getRqId", ""))
    data = em.get_method()
    
    tr_cmd = {
        'rqId': data,
        'trCode': 'OTD3211Q',
        'rqName': 'OutRec2',
        'input': {
            "ACNO": os.getenv("ACNO"),
            "AC_PWD": os.getenv("ACNO_PW"),
            "ITEM_COD": "005930",
            "CMSN_ICLN_YN": "Y"
        },
        'output': ["ITEM_COD", "ITEM_NM", "BAL_Q", "SEL_ABLE_Q", "CRD_TCD", "CLN_DT", "CBAS_PCHS_UPR"]
    }

    codes = ["005930", "000020", "035720"]
    for code in codes:
        tr_cmd['input']['ITEM_COD'] = code
        em.put_tr(tr_cmd)
        data = em.get_tr()
        print(data)