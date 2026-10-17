"""Rule-based baseline: a product-review lexicon with negation, intensifiers, contrast and emoji.

Interpretable on purpose. Every prediction can be explained by the words that moved it.
"""

import math
import re

from app.ml.sentiment.base import Label, Prediction
from app.ml.sentiment.preprocess import preprocess

POSITIVE = {
    # general
    "good": 1.0, "great": 1.5, "excellent": 2.0, "amazing": 2.0, "awesome": 2.0, "fantastic": 2.0, "brilliant": 1.8,
    "love": 1.8, "loving": 1.8, "loved": 1.8, "like": 0.6, "liked": 0.8, "nice": 1.0, "best": 1.8, "better": 1.0,
    "perfect": 2.0, "happy": 1.5, "satisfied": 1.5, "impressed": 1.8, "impressive": 1.8, "recommend": 1.5,
    "worth": 1.2, "superb": 2.0, "outstanding": 2.0, "wonderful": 2.0, "beautiful": 1.6, "gorgeous": 1.8,
    "pleased": 1.4, "glad": 1.0, "enjoy": 1.2, "solid": 1.0, "decent": 0.5, "fine": 0.4, "okay": 0.1,
    "helpful": 1.4, "friendly": 1.2, "patient": 1.0, "reliable": 1.4, "favourite": 1.5, "favorite": 1.5,
    "classy": 1.4, "premium": 1.0, "genuinely": 0.3, "wow": 1.2, "kudos": 1.5, "thanks": 0.6, "thank": 0.6,
    "win": 1.2, "winner": 1.5, "king": 1.2, "fire": 1.4, "crazy good": 1.8, "game changer": 1.8,
    # product performance
    "smooth": 1.4, "smoother": 1.4, "fast": 1.0, "faster": 1.0, "quick": 0.8, "snappy": 1.4, "bright": 0.8,
    "clear": 0.8, "crisp": 1.2, "sharp": 0.8, "loud": 0.6, "lightweight": 0.8, "sturdy": 1.2, "durable": 1.2,
    "clean": 0.8, "easy": 0.8, "intuitive": 1.2, "efficient": 1.0, "long lasting": 1.4, "zero regrets": 1.8,
    "no regrets": 1.8, "value for money": 1.5, "pop": 0.8, "instantly": 0.6, "on time": 0.8, "early": 0.6,
    "resolved": 1.0, "fixed": 0.6, "replaced": 0.4, "smoothly": 1.0, "unreal": 1.0, "nice touch": 1.2,
    # hinglish
    "accha": 1.2, "achha": 1.2, "acha": 1.0, "badhiya": 1.8, "mast": 1.6, "zabardast": 2.0, "kamaal": 1.8,
    "shandaar": 1.8, "paisa vasool": 1.8, "pasand": 1.0, "sahi": 0.8, "kya baat": 1.4,
}

NEGATIVE = {
    # general
    "bad": 1.2, "worse": 1.4, "worst": 2.0, "terrible": 2.0, "horrible": 2.0, "awful": 2.0, "poor": 1.4,
    "hate": 1.8, "disappointing": 1.6, "disappointed": 1.6, "disaster": 2.0, "nightmare": 2.0, "useless": 1.8,
    "waste": 1.8, "regret": 1.6, "annoying": 1.4, "frustrating": 1.6, "unacceptable": 1.8, "overpriced": 1.4,
    "cheap": 0.8, "meh": 0.6, "scam": 2.0, "fake": 1.5, "broken": 1.6, "broke": 1.5, "defect": 1.6,
    "defective": 1.8, "faulty": 1.6, "problem": 1.0, "issue": 0.8, "issues": 0.8, "bug": 1.0, "bugs": 1.0,
    "complain": 1.0, "complaint": 1.2, "never again": 1.8, "rip off": 2.0, "ripoff": 2.0, "scared": 1.0,
    "ugh": 1.0, "seriously?": 0.8, "can't believe": 0.6,
    # product performance
    "slow": 1.2, "lag": 1.4, "lags": 1.4, "laggy": 1.5, "lagging": 1.4, "heats": 1.3, "heating": 1.2,
    "overheats": 1.6, "hot": 0.8, "drains": 1.4, "crash": 1.4, "crashes": 1.4, "crashed": 1.4, "freeze": 1.3,
    "freezes": 1.3, "restarting": 1.2, "stuck": 1.2, "cracked": 1.4, "crackles": 1.2, "blurry": 1.4,
    "dim": 0.6, "dims": 0.8, "tint": 0.8, "scratches": 1.0, "damaged": 1.5, "late": 1.2, "delayed": 1.4,
    "pending": 0.8, "cancelled": 1.0, "drops": 0.8, "disconnect": 1.2, "barely": 0.8, "bloatware": 1.4,
    "ads": 1.0, "creaks": 1.2, "inaccurate": 1.2, "used unit": 1.2, "dead": 1.4, "stopped": 1.0,
    "no reply": 1.4, "not working": 1.6, "doesn't work": 1.6, "can't connect": 1.4, "pricey": 0.6,
    "smoothing": 0.6, "paintings": 0.4,
    # hinglish
    "bekaar": 1.8, "bekar": 1.8, "ghatiya": 2.0, "bakwas": 2.0, "kharab": 1.6, "garam": 1.2, "bura": 1.4,
    "nahi chalta": 1.4, "nahi uthate": 1.4, "slow hai": 1.2,
}

EMOJI = {"👍": 1.2, "❤️": 1.5, "❤": 1.5, "😍": 1.6, "🔥": 1.2, "😊": 1.0, "🙂": 0.6, "👌": 1.0, "💯": 1.2,
         "😡": -1.8, "👎": -1.5, "😠": -1.6, "🤬": -2.0, "😞": -1.2, "😢": -1.0, "🙄": -1.0, "💩": -1.6}

NEGATORS = {"not", "no", "never", "don't", "dont", "can't", "cant", "cannot", "isn't", "isnt", "didn't", "didnt",
            "doesn't", "doesnt", "won't", "wont", "wasn't", "wasnt", "nothing", "nahi", "nahin", "mat", "without"}
INTENSIFIERS = {"very": 1.4, "really": 1.3, "super": 1.4, "so": 1.3, "extremely": 1.6, "absolutely": 1.5,
                "totally": 1.4, "highly": 1.4, "too": 1.2, "way": 1.2, "honestly": 1.1, "ekdum": 1.5, "bahut": 1.4,
                "bilkul": 1.3, "crazy": 1.2, "insanely": 1.5}
# "A but B": the part after "but" carries the verdict. "A though B": the part before does.
CONTRAST_AFTER = {"but", "however", "par", "lekin", "magar", "still"}
CONTRAST_BEFORE = {"though", "although"}

SARCASM_CUES = [
    r"\boh great\b", r"\bjust what i needed\b", r"\bthanks for the\b", r"\btruly premium\b", r"\bgenius\b",
    r"\byeah sure\b", r"\bso glad i paid\b", r"\bwow, only\b", r"\bnothing says\b", r"\bwaah\b",
    r"\blove how\b", r"\bbrilliant idea\b", r"'[^']+'", r"\"[^\"]+\"", r"\breally enhances\b",
]
SARCASM = re.compile("|".join(SARCASM_CUES))
# Problem words that, next to a sarcasm cue, show the "praise" is ironic.
PROBLEM_CONTEXT = re.compile(
    r"\b(update|battery|heat|cook|crack|drop|ads?|lag|weeks?|days?|hours?|reply|charger|focus|kills?|din)\w*"
)

TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?\??|[^\w\s]", re.UNICODE)
LATIN = re.compile(r"[a-z]")

PHRASES = sorted({k for k in (*POSITIVE, *NEGATIVE) if " " in k}, key=len, reverse=True)


def _softmax(values: list[float]) -> list[float]:
    peak = max(values)
    exps = [math.exp(v - peak) for v in values]
    total = sum(exps)
    return [e / total for e in exps]


class LexiconSentiment:
    name = "lexicon"
    version = "lex-1"

    def _score(self, text: str) -> tuple[float, int, int, list[str]]:
        clean = preprocess(text)
        flags: list[str] = []
        # Join known multi-word phrases so they score as one token.
        for phrase in PHRASES:
            clean = clean.replace(phrase, phrase.replace(" ", "_"))
        tokens = TOKEN.findall(clean) + [ch for ch in text if ch in EMOJI]

        contrast_at, before_weight = None, 1.0
        for i, tok in enumerate(tokens):
            if tok in CONTRAST_AFTER:
                contrast_at, before_weight = i, 0.5
            elif tok in CONTRAST_BEFORE:
                contrast_at, before_weight = i, 1.5

        total, pos_hits, neg_hits = 0.0, 0, 0
        for i, tok in enumerate(tokens):
            key = tok.replace("_", " ")
            value = POSITIVE.get(key, 0.0) - NEGATIVE.get(key, 0.0) + EMOJI.get(tok, 0.0)
            if value == 0.0:
                continue
            window = tokens[max(0, i - 3) : i]
            if any(w in NEGATORS for w in window):
                value *= -0.75
            for w in window[-2:]:
                value *= INTENSIFIERS.get(w, 1.0)
            if contrast_at is not None:
                after_weight = 2.0 - before_weight
                value *= before_weight if i < contrast_at else after_weight
            total += value
            pos_hits += value > 0
            neg_hits += value < 0

        if SARCASM.search(clean.replace("_", " ")):
            flags.append("sarcasm_cue")
            if total > 0 and PROBLEM_CONTEXT.search(clean):
                total = -abs(total) - 0.5
        if pos_hits and neg_hits:
            flags.append("mixed")
        if not pos_hits and not neg_hits:
            flags.append("low_signal")
        if not LATIN.search(clean):
            flags.append("unsupported_script")
        return total, pos_hits, neg_hits, flags

    def predict(self, texts: list[str]) -> list[Prediction]:
        results = []
        for text in texts:
            score, _, _, flags = self._score(text)
            probs = _softmax([-score, 0.8 - abs(score), score])
            scores = dict(zip(("negative", "neutral", "positive"), probs, strict=True))
            label: Label = max(scores, key=scores.get)  # type: ignore[arg-type]
            confidence = scores[label]
            if confidence < 0.5:
                flags.append("low_confidence")
            results.append(Prediction(label, round(confidence, 4), {k: round(v, 4) for k, v in scores.items()}, flags))
        return results
