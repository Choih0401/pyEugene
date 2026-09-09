import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    user_id: str = os.getenv("EUGENE_USER_ID", "")
    user_pw: str = os.getenv("EUGENE_USER_PW", "")
    cert_pw: str = os.getenv("EUGENE_CERT_PW", "")

    # Only needed for a 제휴사(partner) 신청계좌 - triggers CommLoginPartner
    # instead of CommLogin. Leave blank for a normal personal account.
    partner_code: str = os.getenv("EUGENE_PARTNER_CODE", "")

    # When true, no real Champion OpenAPI / Windows / brokerage account is
    # touched. A FakeEugeneManager answers every call with synthetic data so
    # the generated Swagger UI can be explored on any OS.
    mock_mode: bool = _bool("EUGENE_MOCK_MODE", True)

    # Required value of the `X-API-Key` header on every request. Refuses to
    # start in real (non-mock) mode if left blank, since this server can
    # place real orders on a real brokerage account.
    api_key: str = os.getenv("EUGENE_API_KEY", "")

    # Order/cancel/amend TR codes (Subject ending in "U") are only
    # registered as routes when this is explicitly enabled - a deliberate
    # extra step before this server can move money.
    enable_trading: bool = _bool("EUGENE_ENABLE_TRADING", False)

    real_snapshot_default_timeout: float = float(os.getenv("EUGENE_REAL_SNAPSHOT_TIMEOUT", "5"))

    # Bounds every TR/method call to pyeugene. Without this, a Champion
    # OpenAPI session that stops responding (dropped connection, etc.)
    # leaves the HTTP request hanging forever - see EugeneService._run().
    call_timeout_seconds: float = float(os.getenv("EUGENE_CALL_TIMEOUT_SECONDS", "30"))


settings = Settings()
