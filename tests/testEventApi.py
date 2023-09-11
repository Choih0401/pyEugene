import sys
import os
from pprint import pprint
from dotenv import load_dotenv
from pyeugene.eugene_manager import EugeneManager

if __name__ == "__main__":
    load_dotenv()
    em = EugeneManager()
    
    while(True):
        data = em.getEvent()
        pprint(data)
    
    sys.exit()