"""TF-IDF + logistic regression benchmark, trained on the labelled set's train split."""

from collections.abc import Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from app.ml.sentiment.base import Label, Prediction
from app.ml.sentiment.dataset import Example, dataset_hash, load_labelled
from app.ml.sentiment.preprocess import preprocess


def build_pipeline(c: float) -> Pipeline:
    features = FeatureUnion(
        [
            ("words", TfidfVectorizer(preprocessor=preprocess, ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("chars", TfidfVectorizer(preprocessor=preprocess, analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
        ]
    )
    return Pipeline(
        [("features", features), ("clf", LogisticRegression(C=c, class_weight="balanced", max_iter=2000, random_state=0))]
    )


class TfidfSentiment:
    name = "tfidf-logreg"

    def __init__(self, train: Sequence[Example] | None = None, c: float = 2.0):
        train = list(train) if train is not None else [e for e in load_labelled() if e.split == "train"]
        self.c = c
        self.version = f"tfidf-1-c{c:g}-{dataset_hash()}"
        self.pipeline = build_pipeline(c).fit([e.text for e in train], [e.label for e in train])

    def predict(self, texts: list[str]) -> list[Prediction]:
        if not texts:
            return []
        probs = self.pipeline.predict_proba(texts)
        classes = list(self.pipeline.classes_)
        results = []
        for row in probs:
            best = int(np.argmax(row))
            label: Label = classes[best]
            confidence = float(row[best])
            flags = ["low_confidence"] if confidence < 0.5 else []
            results.append(Prediction(label, round(confidence, 4), {c: round(float(p), 4) for c, p in zip(classes, row, strict=True)}, flags))
        return results
