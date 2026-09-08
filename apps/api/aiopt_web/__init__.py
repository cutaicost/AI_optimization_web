__version__ = "0.2.0"

# Register public request intake on the already-mounted public router without
# changing the main application module or its in-progress tenant refactor.
from . import provider_api as _provider_api
from .public_requests import router as _public_requests_router
_provider_api.public_router.include_router(_public_requests_router)
