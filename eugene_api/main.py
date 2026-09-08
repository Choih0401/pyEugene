"""
Entrypoint for `uvicorn eugene_api.main:app`.

    EUGENE_MOCK_MODE=true  uvicorn eugene_api.main:app --reload   # explore Swagger, no Windows/account needed
    uvicorn eugene_api.main:app --host 0.0.0.0 --port 8000        # real mode (Windows + Champion OpenAPI required)
"""
from eugene_api.app_factory import build_app

app = build_app()
