__version__ = "1.7.4"

# Extend the v1.7 curator with a larger, still-curated context pool before
# app.main imports the legacy-named workshop_v16 module.
from . import workshop_v171_expansion as _workshop_v171_expansion

_workshop_v171_expansion.install()

# v1.7.4 keeps the existing service contract but replaces the concrete service
# class with an adaptive-depth implementation before app.main imports it.
from . import service as _service
from .service_v174 import DeepNameLabService as _DeepNameLabService

_service.NameLabService = _DeepNameLabService
