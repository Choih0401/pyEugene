import sys
import os
from dotenv import load_dotenv
from pyeugene.eugene_manager import EugeneManager

if __name__ == "__main__":
    load_dotenv()
    em = EugeneManager(os.getenv("USER_ID"), os.getenv("USER_PW"), os.getenv("CERT_PW"))

    while True:
        data = em.getEvent()
        print(data)
    
    sys.exit()