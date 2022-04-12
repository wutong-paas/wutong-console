from starlette.middleware.cors import CORSMiddleware

from core.setting import settings
from middleware.access_middle import AccessMiddleware

def register_middleware(app):
    app.add_middleware(AccessMiddleware)
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(CORSMiddleware,
                           allow_origins=settings.BACKEND_CORS_ORIGINS,
                           allow_credentials=True,
                           allow_methods=["*"],
                           allow_headers=["*"],
                           expose_headers=["Content-Disposition"]
                           )
