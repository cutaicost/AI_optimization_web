__version__ = "0.2.0"

# Register public request intake and platform-admin ticket browsing on the
# already-mounted public router without changing the main application module.
from . import provider_api as _provider_api
from .public_requests import admin_router as _request_admin_router, router as _public_requests_router
_provider_api.public_router.include_router(_public_requests_router)
_provider_api.public_router.include_router(_request_admin_router)
