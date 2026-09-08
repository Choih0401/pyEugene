from fastapi import Header, HTTPException, status

from eugene_api.config import settings

_API_KEY_HEADER = "X-API-Key"


async def verify_api_key(x_api_key: str = Header(default="", alias=_API_KEY_HEADER)) -> None:
    if not settings.api_key:
        # Only reachable in mock mode - config.build_app() refuses to start
        # a non-mock server without EUGENE_API_KEY set.
        return
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing X-API-Key header")
