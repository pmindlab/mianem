__version__ = "1.7.4"

# Extend the v1.7 curator with a larger, still-curated context pool before
# app.main imports the legacy-named workshop_v16 module.
from . import workshop_v171_expansion as _workshop_v171_expansion

_workshop_v171_expansion.install()

# v1.7.4 portable/state recovery baseline.
from . import service as _service
from .service_v174 import DeepNameLabService as _DeepNameLabService

_service.NameLabService = _DeepNameLabService

# Search v2 is stacked on top of the v1.7.4 safety baseline. It expands discovery
# sources and live-check depth without weakening availability or quality invariants.
from .service_v18 import SearchV2Service as _SearchV2Service

_service.NameLabService = _SearchV2Service
