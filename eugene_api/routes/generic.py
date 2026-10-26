from typing import Dict

from fastapi import APIRouter

from eugene_api.catalog import RealSpec, TranSpec
from eugene_api.config import settings


def build_generic_router(tran_catalog: Dict[str, TranSpec], real_catalog: Dict[str, RealSpec]) -> APIRouter:
    router = APIRouter(tags=["메타"])

    @router.get("/health", summary="서버 상태 확인")
    async def health():
        return {
            "status": "ok",
            "mock_mode": settings.mock_mode,
            "trading_enabled": settings.enable_trading,
            "tran_codes": len(tran_catalog),
            "real_ids": len(real_catalog),
        }

    @router.get("/catalog/tran", summary="등록된 모든 TR 코드 목록 (Swagger 경로 포함)")
    async def catalog_tran():
        return [
            {
                "code": s.code,
                "title": s.title,
                "continuable": s.continuable,
                "mutating": s.is_mutating,
                "path": f"/tran/{s.code}" if (not s.is_mutating or settings.enable_trading) else None,
                "input_fields": [f.item for f in s.input],
                "output_fields": [f.item for f in s.output_single] + [f.item for f in s.output_multi],
            }
            for s in sorted(tran_catalog.values(), key=lambda s: s.code)
        ]

    @router.get("/catalog/real", summary="등록된 모든 Real ID 목록 (Swagger 경로 포함)")
    async def catalog_real():
        return [
            {
                "real_id": s.real_id,
                "code": s.code,
                "title": s.title,
                "snapshot_path": f"/real/{s.code}/snapshot",
                "websocket_path": f"/ws/real/{s.code}",
                "output_fields": [f.item for f in s.output],
            }
            for s in sorted(real_catalog.values(), key=lambda s: s.code)
        ]

    return router
