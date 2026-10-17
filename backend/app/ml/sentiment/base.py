from dataclasses import dataclass, field
from typing import Literal, Protocol

Label = Literal["negative", "neutral", "positive"]
LABELS: tuple[Label, ...] = ("negative", "neutral", "positive")

# Bump when preprocess() changes, so stored predictions can be traced to the text they saw.
PREPROCESSING_VERSION = "pre-1"


@dataclass(frozen=True)
class Prediction:
    label: Label
    confidence: float
    scores: dict[str, float]
    # Reasons to trust this label less: mixed, sarcasm_cue, low_signal, low_confidence, unsupported_script.
    flags: list[str] = field(default_factory=list)


class SentimentModel(Protocol):
    name: str
    version: str

    def predict(self, texts: list[str]) -> list[Prediction]: ...
