"""Local smoke test for eugene_api in mock mode - no Windows/pyeugene needed."""
import json
import os

os.environ.setdefault("EUGENE_MOCK_MODE", "true")
os.environ.setdefault("EUGENE_API_KEY", "")

from fastapi.testclient import TestClient

from eugene_api.app_factory import build_app

app = build_app()

with TestClient(app) as client:
    print("== /health ==")
    r = client.get("/health")
    print(r.status_code, r.json())

    print("\n== openapi.json builds OK? ==")
    r = client.get("/openapi.json")
    print(r.status_code, "paths:", len(r.json()["paths"]))

    print("\n== /catalog/tran (first 3) ==")
    r = client.get("/catalog/tran")
    data = r.json()
    print(r.status_code, "total:", len(data))
    print(json.dumps(data[:3], ensure_ascii=False, indent=2))

    print("\n== POST /tran/OTD3211Q (매도 가능 수량) ==")
    r = client.post("/tran/OTD3211Q", json={"ACNO": "12345678901", "AC_PWD": "0000", "ITEM_COD": "005930", "CMSN_ICLN_YN": "Y"})
    print(r.status_code)
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))

    print("\n== POST /tran/OTD1101U should be absent (trading disabled by default) ==")
    r = client.post("/tran/OTD1101U", json={})
    print(r.status_code)

    print("\n== /catalog/real (first 3) ==")
    r = client.get("/catalog/real")
    data = r.json()
    print(r.status_code, "total:", len(data))
    print(json.dumps(data[:3], ensure_ascii=False, indent=2))

    print("\n== GET /real/S00/snapshot?key=005930&timeout=3 ==")
    r = client.get("/real/S00/snapshot", params={"key": "005930", "timeout": 3})
    print(r.status_code)
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))

    print("\n== /utils/exp-code ==")
    r = client.get("/utils/exp-code", params={"sh_code": "005930"})
    print(r.status_code, r.json())

print("\nOK")
