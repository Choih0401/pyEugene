import sys
import os
from pprint import pprint
from dotenv import load_dotenv
from eugene_manager import EugeneManager

if __name__ == "__main__":
    em = EugeneManager()
    load_dotenv()

    while(True):
      data = em.getEvent()
      pprint(data)

    sys.exit()