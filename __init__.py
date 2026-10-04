from .data_provider import provider
from .routes import assistant_bp

# A short name used by app.py to plug in a data source (Gmail, Calendar, ...)
register_source = provider.register

__all__ = ["assistant_bp", "provider", "register_source"]
