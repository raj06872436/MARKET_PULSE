import re

URL = re.compile(r"https?://\S+|www\.\S+")
MENTION = re.compile(r"@\w+")
REPEATS = re.compile(r"(\w)\1{2,}")


def preprocess(text: str) -> str:
    """Normalize social text before scoring (see PREPROCESSING_VERSION in base.py)."""
    text = URL.sub(" ", text)
    text = MENTION.sub(" @user ", text)
    text = text.replace("#", " ")
    text = REPEATS.sub(r"\1\1", text)  # "soooo" -> "soo"
    return " ".join(text.lower().split())
