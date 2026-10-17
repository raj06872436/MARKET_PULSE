"""Optional pretrained transformer candidate. Not a runtime dependency.

Install requirements-ml-optional.txt and allow access to huggingface.co, then run the evaluation
with --transformer. Confirm the model's licence allows your use before promoting it.
"""

from app.ml.sentiment.base import Label, Prediction

DEFAULT_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
LABEL_MAP = {"negative": "negative", "neutral": "neutral", "positive": "positive",
             "label_0": "negative", "label_1": "neutral", "label_2": "positive"}


class TransformerSentiment:
    name = "transformer"

    def __init__(self, model_id: str = DEFAULT_MODEL):
        from transformers import pipeline  # imported lazily so the app never needs torch

        self.version = model_id
        self.pipe = pipeline("text-classification", model=model_id, top_k=None, truncation=True)

    def predict(self, texts: list[str]) -> list[Prediction]:
        results = []
        for scores in self.pipe(texts, batch_size=16):
            mapped = {LABEL_MAP[s["label"].lower()]: float(s["score"]) for s in scores}
            label: Label = max(mapped, key=mapped.get)  # type: ignore[arg-type]
            confidence = mapped[label]
            results.append(Prediction(label, round(confidence, 4), mapped, ["low_confidence"] if confidence < 0.5 else []))
        return results
