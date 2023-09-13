import sys
import os
from pprint import pprint
from dotenv import load_dotenv
from pyeugene.eugene_manager import EugeneManager

if __name__ == "__main__":
    load_dotenv()
    em = EugeneManager(os.getenv("USER_ID"), os.getenv("USER_PW"), os.getenv("CERT_PW"))

    em.put_method(("getRqId", ""))
    data = em.get_method()
    
    tr_cmd = {
        'rqId': data,
        'trCode': 'OTD3211Q',
        'input': {
            "ACNO": os.getenv("ACNO"),
            "AC_PWD": os.getenv("ACNO_PW"),
            "ITEM_COD": "",
            "CMSN_ICLN_YN": "Y"
        },
        'output': {
            'OutRec1': ['RECNM', 'AC_NM'],
            'OutRec2': ["ITEM_COD", "ITEM_NM", "BAL_Q", "SEL_ABLE_Q", "CRD_TCD", "CLN_DT", "CBAS_PCHS_UPR"]
        }
    }

    codes = ["005930", "000020", "035720"]
    for code in codes:
        tr_cmd['input']['ITEM_COD'] = code
        em.put_tr(tr_cmd)
        data = em.get_tr()
        print(data)
    em.put_method(("releaseRqId", data))