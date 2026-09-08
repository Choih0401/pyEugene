import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from eugene_api.catalog import build_quality_report, load_real_catalog, load_tran_catalog
from eugene_api.config import settings
from eugene_api.routes.generic import build_generic_router
from eugene_api.routes.real import register_real_routes
from eugene_api.routes.tran import register_tran_routes
from eugene_api.routes.utils import build_utils_router
from eugene_api.service import EugeneService, RealDispatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eugene_api")


def _create_manager():
    if settings.mock_mode:
        from eugene_api.mock_manager import FakeEugeneManager

        logger.warning(
            "EUGENE_MOCK_MODE=true -> using FakeEugeneManager. No real Champion OpenAPI, "
            "Windows OCX, or brokerage account is involved; all TR/Real responses are synthetic."
        )
        return FakeEugeneManager()

    if not (settings.user_id and settings.user_pw):
        raise RuntimeError("EUGENE_USER_ID and EUGENE_USER_PW must be set when EUGENE_MOCK_MODE=false")

    # Only importable on 32-bit Windows with pywin32/PyQt5 and the Champion
    # OpenAPI OCX installed - see pyeugene/eugene_proxy.py.
    from pyeugene.eugene_manager import EugeneManager

    return EugeneManager(
        settings.user_id, settings.user_pw, settings.cert_pw,
        partner_code=settings.partner_code or None,
    )


def build_app() -> FastAPI:
    if not settings.mock_mode and not settings.api_key:
        raise RuntimeError(
            "EUGENE_API_KEY must be set before starting in real mode - "
            "this server can submit real brokerage orders once EUGENE_ENABLE_TRADING=true."
        )

    tran_catalog = load_tran_catalog()
    real_catalog = load_real_catalog()

    report = build_quality_report(tran_catalog, real_catalog)
    if report["tran"] or report["real"]:
        logger.warning(
            "catalog parsing had to drop some malformed fields for %d TR code(s) and %d Real ID(s); "
            "see GET /catalog/tran and /catalog/real, or re-run tools/parse_catalog.py, for details",
            len(report["tran"]), len(report["real"]),
        )

    service = EugeneService()
    dispatcher = RealDispatcher()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manager = _create_manager()
        service.set_manager(manager)
        dispatcher.start(manager, asyncio.get_running_loop())
        logger.info(
            "eugene_api ready: %d TR routes requested, %d Real IDs, trading_enabled=%s, mock_mode=%s",
            len(tran_catalog), len(real_catalog), settings.enable_trading, settings.mock_mode,
        )
        yield

    app = FastAPI(
        title="Eugene Champion OpenAPI REST Gateway",
        description=(
            "유진투자증권 Champion OpenAPI를 감싸는 pyeugene 위에서, TRAN서비스IO.pdf / "
            "Real서비스IO.pdf 문서를 파싱해 자동 생성한 REST API입니다.\n\n"
            f"- TR(조회/주문) 엔드포인트: {len(tran_catalog)}개\n"
            f"- 실시간(Real) 엔드포인트: {len(real_catalog)}개\n\n"
            "모든 요청에는 `X-API-Key` 헤더가 필요합니다 (EUGENE_API_KEY). "
            "주문/정정/취소류(TR 코드가 'U'로 끝남) 엔드포인트는 EUGENE_ENABLE_TRADING=true 일 때만 노출됩니다."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(build_generic_router(tran_catalog, real_catalog))
    app.include_router(build_utils_router(service))
    register_tran_routes(app, service, tran_catalog, allow_trading=settings.enable_trading)
    register_real_routes(app, service, dispatcher, real_catalog)

    return app
