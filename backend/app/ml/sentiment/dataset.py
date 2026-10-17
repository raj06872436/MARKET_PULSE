import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

LABELLED_PATH = Path(__file__).parent / "data" / "labelled.csv"


@dataclass(frozen=True)
class Example:
    id: str
    text: str
    label: str
    tags: tuple[str, ...]
    split: str


def load_labelled(path: Path = LABELLED_PATH) -> list[Example]:
    with path.open(encoding="utf-8") as f:
        return [
            Example(r["id"], r["text"], r["label"], tuple(t for t in r["tags"].split(";") if t), r["split"])
            for r in csv.DictReader(f)
        ]


def dataset_hash(path: Path = LABELLED_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]
