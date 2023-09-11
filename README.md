# pyEugene 📈

[![Publish to Pypi](https://github.com/Choih0401/pyEugene/actions/workflows/publish.yml/badge.svg)](https://github.com/Choih0401/pyEugene/actions/workflows/publish.yml)
[![PyPI version](https://badge.fury.io/py/pyeugene.svg)](https://badge.fury.io/py/pyeugene)
[![Downloads](https://static.pepy.tech/personalized-badge/pyeugene?period=month&units=international_system&left_color=grey&right_color=brightgreen&left_text=Downloads)](https://pepy.tech/project/pyeugene)


Eugene Investment & Securities Champion Open Api Python Wrapper

Free software: [`MIT`](https://github.com/Choih0401/pyEugene/blob/main/LICENSE)

## Demo

![Demo](https://raw.githubusercontent.com/Choih0401/pyEugene/master/images/testRealApi.gif)

## Prerequisites 👓

- Python 3.9.*
- 32 Bit Development environment
- Eugene Web Account (need Eugene securities account)

## Introduction 💻

pyEugene is an unofficial python wrapper for easy use of the Champion Open API provided by Eugene Investment & Securities.

Even if you are not familiar with the functions below, you can use all of them.

* The API structure of OCX provided by Eugene Investment & Securities
* Operating Structure of the Version Processing Program Provided by Eugene Investment & Securities
* Use [`dynamicCall`](https://doc.qt.io/qt-5/qaxbase.html#dynamicCall) function for function invocation in control

<details>
<summary>Korean Introduction</summary>
pyEugene은 유진투자증권에서 제공하는 Champion Open API를 쉽게 사용하기 위한 비공식 python wrapper입니다.

아래의 기능들을 잘 모르더라도 충분히 모든 기능을 사용할 수 있습니다.

* 유진투자증권에서 제공하는 OCX의 API 구조
* 유진투자증권에서 제공하는 버전처리 프로그램의 작동 구조
* 컨트롤에서 함수 호출을 위한 [`dynamicCall`](https://doc.qt.io/qt-5/qaxbase.html#dynamicCall) 함수 사용
</details>

## Getting Started 🚀

To begin using `pyEugene`, start by installing anaconda(or you can use miniconda):

[Download anaconda](https://www.anaconda.com/download/)
[Download miniconda](https://docs.conda.io/projects/miniconda/en/latest/index.html)

When you're done installing the anaconda, run the anaconda prompt and set it to a 32-bit development environment

```sh
set CONDA_FORCE_32BIT=1
```

If you replace the anaconda with 32-bit, create a 32-bit virtual environment
(You should use Python 3.9 version)

```sh
conda create --name py39_32 python=3.9
```

When you're done installing, activate virtual environment and use the pip to install `pyEugene`

```sh
conda activate py39_32
pip install pyeugene
```

Once you've installed `pyEugene`, you can start using it right away.
For example, to get real-time stock price using `pyEugene`, enter the following code:

```python
import sys
import os
from pprint import pprint
from dotenv import load_dotenv
from pyeugene.eugene_manager import EugeneManager

if __name__ == "__main__":
    load_dotenv()
    em = EugeneManager(os.getenv("USER_ID"), os.getenv("USER_PW"), os.getenv("CERT_PW"))

    real_cmd = {
        'realId': '21',
        'realKey': '005930',
        'output': ["SCODE", "SNAME", "CMARKETGUBUN", "LTIME", "CPCHECK", "LDIFF", "LCPRICE"]
    }

    em.put_real(real_cmd)
    for i in range(10):
        data = em.get_real()
        pprint(data)
    sys.exit()
```

## Contributions 💬

Feel free to contribute to `pyEugene` fixing bugs.