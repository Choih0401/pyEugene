"""
Hand-written wrappers for the handful of Champion OpenAPI "부가기능/종목코드"
utility Methods (section 4.1 of the dev guide) that aren't TR/Real calls -
code<->name lookups, login state, account list. Small and stable enough
that generating them from a parsed table wasn't worth it.
"""
from fastapi import APIRouter, Depends, Query

from eugene_api.security import verify_api_key
from eugene_api.service import EugeneService


def build_utils_router(service: EugeneService) -> APIRouter:
    router = APIRouter(prefix="/utils", tags=["부가기능/종목코드"], dependencies=[Depends(verify_api_key)])

    @router.get("/login-state", summary="로그인 상태 확인 (GetLoginState)")
    async def login_state():
        state = await service.call_method("getLoginState", "")
        return {"loginState": state, "connected": state == 1}

    @router.get("/account-info", summary="사용 가능 계좌 목록 (GetAccCnt + GetAccInfo)")
    async def account_info():
        cnt = await service.call_method("getAccCnt", "")
        info = await service.call_method("getAccInfo", "")
        return {"accountCount": cnt, "accounts": info}

    @router.get("/exp-code", summary="단축코드 → 표준코드 변환 (GetExpCode)")
    async def exp_code(sh_code: str = Query(..., description="단축코드, 예: 005930")):
        return {"expCode": await service.call_method("getExpCode", sh_code)}

    @router.get("/sh-code", summary="표준코드 → 단축코드 변환 (GetShCode)")
    async def sh_code(exp_code: str = Query(..., description="표준코드")):
        return {"shCode": await service.call_method("getShCode", exp_code)}

    @router.get("/sh-code-by-name", summary="종목명 → 단축코드 (GetShCodeByName)")
    async def sh_code_by_name(name: str = Query(..., description="종목명, 예: 삼성전자")):
        return {"shCode": await service.call_method("getShCodeByName", name)}

    @router.get("/name-by-code", summary="코드 → 종목명 (GetNameByCode)")
    async def name_by_code(code: str = Query(..., description="단축코드 또는 표준코드")):
        return {"name": await service.call_method("getNameByCode", code)}

    @router.get("/upjong-by-code", summary="코드 → 업종코드 (GetUpjongByCode)")
    async def upjong_by_code(code: str = Query(...)):
        return {"upjongCode": await service.call_method("getUpjongByCode", code)}

    @router.get("/market-kubun", summary="종목코드 → 장구분 (GetMarketKubun)")
    async def market_kubun(code: str = Query(...)):
        return {"marketKubun": await service.call_method("getMarketKubun", code)}

    @router.get("/last-error", summary="마지막 오류 메시지 (GetLastErrMsg)")
    async def last_error():
        return {"message": await service.call_method("getLastErrMsg", "")}

    return router
