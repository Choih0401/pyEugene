"""Registers one POST /tran/{code} route per TR code in the catalog."""
import logging
from typing import Dict

from fastapi import Depends, FastAPI, HTTPException, Query, status

from eugene_api.catalog import TranSpec
from eugene_api.dynamic_models import build_tran_input_model, build_tran_output_model
from eugene_api.security import verify_api_key
from eugene_api.service import EugeneService

logger = logging.getLogger("eugene_api")

# TR codes that are registered in the catalog but pyeugene cannot actually
# execute correctly yet (see README_API.md "Known limitations"). Rather
# than silently calling a broken path, these get a clear 501 instead of the
# normal handler.
UNSUPPORTED_CODES = {
    "OTD1103U": (
        "주식그룹주문은 pyeugene의 SetTranInputArrayData/SetTranInputArrayCnt가 필요하지만 "
        "아직 구현되어 있지 않아 (eugene_proxy.py는 flat SetTranInputData만 호출) 이 TR은 "
        "정상적으로 처리되지 않습니다. 정확한 dynamicCall 시그니처가 필요합니다."
    ),
}


def _describe(spec: TranSpec) -> str:
    lines = [spec.description or spec.title]
    if spec.code in UNSUPPORTED_CODES:
        lines.append("⛔ 현재 지원되지 않음: " + UNSUPPORTED_CODES[spec.code])
    if spec.continuable:
        lines.append(
            f"연속조회 여부: {spec.continuable}. `next_key`/`request_cnt` 쿼리 파라미터로 다음 페이지를 "
            "요청할 수 있습니다 - 단, 이 TR의 다음키 값을 응답의 어느 필드에서 가져와야 하는지는 "
            "원본 TRAN서비스IO.pdf에서 직접 확인하세요 (pyeugene은 페이징 자체는 지원하지만, "
            "TR별 다음키 필드를 자동으로 추출해주지는 않습니다)."
        )
    if spec.dropped_fields:
        lines.append(
            "⚠ 이 TR의 필드 목록 일부는 PDF 파싱 중 값이 깨져 제외되었습니다. "
            "정확한 전체 필드는 원본 TRAN서비스IO.pdf의 Subject `%s` 항목을 참고하세요." % spec.code
        )
    return "\n\n".join(lines)


def make_tran_handler(spec: TranSpec, input_model, output_model, service: EugeneService):
    if spec.code in UNSUPPORTED_CODES:
        reason = UNSUPPORTED_CODES[spec.code]

        async def handler(payload: input_model):  # noqa: ANN001 - dynamic type is intentional
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=reason)

        handler.__name__ = f"tran_{spec.code}"
        return handler

    async def handler(
        payload: input_model,  # noqa: ANN001 - dynamic type is intentional
        next_key: str = Query("", description="연속조회 다음키 (모르면 비워두면 첫 페이지)"),
        request_cnt: int = Query(20, ge=1, le=100, description="조회 건수"),
    ):
        raw = await service.call_tran(spec, payload.model_dump(), next_key=next_key, request_cnt=request_cnt)
        return output_model(**raw)

    handler.__name__ = f"tran_{spec.code}"
    return handler


def register_tran_routes(app: FastAPI, service: EugeneService, catalog: Dict[str, TranSpec], allow_trading: bool) -> None:
    registered, skipped = 0, []
    for code, spec in sorted(catalog.items()):
        if spec.is_mutating and not allow_trading:
            skipped.append(code)
            continue

        input_model = build_tran_input_model(spec)
        output_model = build_tran_output_model(spec)
        tag = "TRAN · 주문/처리 (실거래)" if spec.is_mutating else "TRAN · 조회"

        app.add_api_route(
            f"/tran/{code}",
            make_tran_handler(spec, input_model, output_model, service),
            methods=["POST"],
            response_model=output_model,
            summary=spec.title,
            description=_describe(spec),
            tags=[tag],
            operation_id=f"tran_{code}",
            dependencies=[Depends(verify_api_key)],
        )
        registered += 1

    logger.info("registered %d /tran routes (%d order/cancel codes skipped, set EUGENE_ENABLE_TRADING=true to expose them)",
                registered, len(skipped))
