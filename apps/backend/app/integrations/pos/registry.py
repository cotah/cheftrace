"""Single entry point for resolving a POS adapter from a provider name.

Endpoints take the provider as a path parameter and hand it here.
Adding a new provider is one branch in this function plus its concrete
adapter module — no caller changes.
"""

from app.core.config import settings
from app.integrations.pos.base import POSAdapter
from app.integrations.pos.square_adapter import SquarePOSAdapter


def get_pos_adapter(provider: str) -> POSAdapter:
    """Return the concrete adapter for `provider` or raise ValueError.

    Settings the adapter needs (signing URLs, base API URLs) are pulled
    from app.core.config.settings here so callers stay simple.
    """
    if provider == "square":
        if not settings.square_webhook_url:
            raise RuntimeError(
                "SQUARE_WEBHOOK_URL is not configured. "
                "Set it in the backend environment to verify Square webhooks."
            )
        return SquarePOSAdapter(notification_url=settings.square_webhook_url)
    raise ValueError(f"Unknown POS provider: {provider!r}")
