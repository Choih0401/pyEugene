"""
Registers, per Real ID in the catalog:
  * GET  /real/{code}/snapshot  - subscribes, waits for the next matching
    update (bounded by `timeout`), returns it, then unsubscribes. Shows up
    in Swagger with a proper "Try it out" - the practical way to see a real
    endpoint's shape without a WebSocket client.
  * WS   /ws/real/{code}?key=...  - continuous push for as long as the
    socket stays open. OpenAPI/Swagger has no schema for WebSocket routes,
    so this is documented in the summary text instead.
"""
import asyncio
import logging
from typing import Dict

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from eugene_api.catalog import RealSpec
from eugene_api.config import settings
from eugene_api.dynamic_models import build_real_output_model
from eugene_api.service import EugeneService, RealDispatcher

logger = logging.getLogger("eugene_api")


def _check_api_key(x_api_key: str) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing X-API-Key header")


def _describe(spec: RealSpec) -> str:
    lines = [spec.description or spec.title]
    if spec.real_code_desc:
        lines.append("Real Code(key) 형식: " + " ".join(spec.real_code_desc))
    lines.append(
        f"WebSocket 스트리밍: `/ws/real/{spec.code}?key=<realKey>&api_key=<API 키>` "
        "(연속 수신, Swagger UI에는 스키마가 표시되지 않습니다)"
    )
    if spec.dropped_fields:
        lines.append(
            "⚠ 이 Real ID의 필드 목록 일부는 PDF 파싱 중 값이 깨져 제외되었습니다. "
            f"정확한 전체 필드는 원본 Real서비스IO.pdf의 Subject `{spec.code}` 항목을 참고하세요."
        )
    return "\n\n".join(lines)


def make_snapshot_handler(spec: RealSpec, output_model, dispatcher: RealDispatcher, service: EugeneService):
    async def handler(
        key: str = Query(..., description="종목코드 등 Real Code 값 (예: 표준코드 또는 단축코드)"),
        timeout: float = Query(settings.real_snapshot_default_timeout, ge=0.5, le=60,
                                description="초 단위 대기 시간"),
        x_api_key: str = Header(default="", alias="X-API-Key"),
    ):
        _check_api_key(x_api_key)
        q = await dispatcher.subscribe(spec, key)
        try:
            try:
                data = await asyncio.wait_for(q.get(), timeout=timeout)
            except asyncio.TimeoutError:
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail=f"{timeout}초 내에 realId={spec.real_id} key={key} 데이터가 수신되지 않았습니다",
                )
            return output_model(**data)
        finally:
            was_last = dispatcher.unsubscribe(spec, key, q)
            if was_last:
                await service.unregister_real(spec.real_id, key)

    handler.__name__ = f"real_snapshot_{spec.code}"
    return handler


def make_ws_handler(spec: RealSpec, dispatcher: RealDispatcher, service: EugeneService):
    async def handler(
        websocket: WebSocket,
        key: str = Query(...),
        api_key: str = Query(default=""),
    ):
        if settings.api_key and api_key != settings.api_key:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        q = await dispatcher.subscribe(spec, key)
        try:
            while True:
                data = await q.get()
                await websocket.send_json(data)
        except WebSocketDisconnect:
            pass
        finally:
            was_last = dispatcher.unsubscribe(spec, key, q)
            if was_last:
                await service.unregister_real(spec.real_id, key)

    return handler


def register_real_routes(app: FastAPI, service: EugeneService, dispatcher: RealDispatcher, catalog: Dict[str, RealSpec]) -> None:
    for real_id, spec in sorted(catalog.items(), key=lambda kv: kv[1].code):
        output_model = build_real_output_model(spec)

        app.add_api_route(
            f"/real/{spec.code}/snapshot",
            make_snapshot_handler(spec, output_model, dispatcher, service),
            methods=["GET"],
            response_model=output_model,
            summary=f"{spec.title} (스냅샷 1건 대기)",
            description=_describe(spec),
            tags=["REAL · 실시간"],
            operation_id=f"real_snapshot_{spec.code}",
        )

        app.add_api_websocket_route(
            f"/ws/real/{spec.code}",
            make_ws_handler(spec, dispatcher, service),
            name=f"ws_real_{spec.code}",
        )

    logger.info("registered %d /real snapshot+websocket route pairs", len(catalog))
