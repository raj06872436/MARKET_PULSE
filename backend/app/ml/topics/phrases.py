"""Frequent and emerging phrases. Unreviewed: shown as phrases, never as named themes."""

import re
from collections import Counter
from collections.abc import Iterable

from app.ml.sentiment.preprocess import preprocess

STOPWORDS = set(
    """a an the and or but if of to in on at for from by with about as is are was were be been being it its this that
    these those i me my we our you your he she they them his her their what which who whom how when where why all any
    both each few more most other some such no nor not only own same so than too very can will just don should now
    do does did has have had having am also get got im i'm it's its dont can't cant really one ever even still yet
    hai ka ki ke ko se toh bhi mein hi nahi yeh wo yaar kya ek""".split()
)
WORD = re.compile(r"[a-z][a-z0-9']+")


PUNCTUATION = re.compile(r"[,.;:!?()\[\]\"]+")


def phrases(text: str, exclude: set[str]) -> set[str]:
    """2- and 3-word phrases that don't cross punctuation or start/end with a stopword."""
    found = set()
    for segment in PUNCTUATION.split(preprocess(text)):
        words = [w for w in WORD.findall(segment) if w not in exclude]
        for n in (2, 3):
            for i in range(len(words) - n + 1):
                gram = words[i : i + n]
                if gram[0] in STOPWORDS or gram[-1] in STOPWORDS:
                    continue
                found.add(" ".join(gram))
    return found


def top_phrases(texts: Iterable[str], exclude_terms: Iterable[str], limit: int = 10, min_count: int = 3) -> list[tuple[str, int]]:
    """Phrases appearing in at least `min_count` posts, most frequent first. Each post counts once per phrase."""
    exclude = {w for term in exclude_terms for w in WORD.findall(preprocess(term))}
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(phrases(text, exclude))
    ranked = sorted(((p, c) for p, c in counts.items() if c >= min_count), key=lambda pc: (-pc[1], -len(pc[0]), pc[0]))
    # Drop a phrase when a longer phrase containing it is just as frequent.
    kept: list[tuple[str, int]] = []
    for phrase, count in ranked:
        if any(phrase in longer and count <= c for longer, c in kept):
            continue
        kept.append((phrase, count))
    return kept[:limit]
