from app.connectors.base import SourceConnector
from app.connectors.bluesky import BlueskyConnector
from app.core.config import Settings

CONNECTORS: dict[str, type] = {"bluesky": BlueskyConnector}

LABELS = {"bluesky": "Bluesky"}


def build_connector(source: str, settings: Settings) -> SourceConnector:
    return CONNECTORS[source](settings)
