"""Evaluate sentiment models on the labelled set and write the report.

    python -m app.ml.sentiment.evaluate            # lexicon + TF-IDF
    python -m app.ml.sentiment.evaluate --transformer

Model choices (TF-IDF regularization, which model is active) are made on the validation split.
The test split is only scored once, for the report.
"""

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from app.ml.sentiment.base import LABELS, PREPROCESSING_VERSION, Prediction, SentimentModel
from app.ml.sentiment.dataset import Example, dataset_hash, load_labelled
from app.ml.sentiment.lexicon import LexiconSentiment
from app.ml.sentiment.tfidf import TfidfSentiment

EVALUATION_PATH = Path(__file__).parent / "evaluation.json"
REPORT_PATH = Path(__file__).parents[4] / "docs" / "evaluation" / "sentiment.md"
C_GRID = (0.5, 1.0, 2.0, 5.0, 10.0)


def macro_f1(y_true: list[str], y_pred: list[str]) -> float:
    return float(precision_recall_fscore_support(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)[2])


def expected_calibration_error(preds: list[Prediction], y_true: list[str], bins: int = 5) -> float:
    buckets: dict[int, list[tuple[float, bool]]] = defaultdict(list)
    for p, t in zip(preds, y_true, strict=True):
        buckets[min(int(p.confidence * bins), bins - 1)].append((p.confidence, p.label == t))
    total = len(preds)
    return sum(
        len(items) / total * abs(sum(c for c, _ in items) / len(items) - sum(ok for _, ok in items) / len(items))
        for items in buckets.values()
    )


def score(model: SentimentModel, examples: list[Example]) -> dict:
    preds = model.predict([e.text for e in examples])
    y_true = [e.label for e in examples]
    y_pred = [p.label for p in preds]
    precision, recall, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, zero_division=0)
    by_tag: dict[str, list[int]] = defaultdict(list)
    for i, e in enumerate(examples):
        for tag in e.tags or ("plain",):
            by_tag[tag].append(i)
    flagged = [i for i, p in enumerate(preds) if p.flags]
    return {
        "n": len(examples),
        "accuracy": round(sum(t == p for t, p in zip(y_true, y_pred, strict=True)) / len(examples), 4),
        "macro_f1": round(macro_f1(y_true, y_pred), 4),
        "per_class": {
            label: {"precision": round(float(precision[i]), 4), "recall": round(float(recall[i]), 4),
                    "f1": round(float(f1[i]), 4), "support": int(support[i])}
            for i, label in enumerate(LABELS)
        },
        "confusion_matrix": {"labels": list(LABELS), "rows_true_cols_pred": confusion_matrix(y_true, y_pred, labels=LABELS).tolist()},
        "ece": round(expected_calibration_error(preds, y_true), 4),
        "by_tag": {
            tag: {"n": len(idx), "accuracy": round(sum(y_true[i] == y_pred[i] for i in idx) / len(idx), 4)}
            for tag, idx in sorted(by_tag.items())
        },
        "flagged_share": round(len(flagged) / len(examples), 4),
        "flagged_accuracy": round(sum(y_true[i] == y_pred[i] for i in flagged) / len(flagged), 4) if flagged else None,
        "errors": [
            {"id": e.id, "text": e.text, "true": t, "pred": p.label, "confidence": p.confidence, "flags": p.flags}
            for e, t, p in zip(examples, y_true, preds, strict=True) if t != p.label
        ],
    }


def run(include_transformer: bool = False) -> dict:
    data = load_labelled()
    train = [e for e in data if e.split == "train"]
    validation = [e for e in data if e.split == "validation"]
    test = [e for e in data if e.split == "test"]

    c_search = {c: macro_f1([e.label for e in validation], [p.label for p in TfidfSentiment(train, c).predict([e.text for e in validation])]) for c in C_GRID}
    best_c = max(C_GRID, key=lambda c: (round(c_search[c], 4), -c))

    candidates: dict[str, SentimentModel] = {"lexicon": LexiconSentiment(), "tfidf-logreg": TfidfSentiment(train, best_c)}
    notes: dict[str, str] = {}
    if include_transformer:
        try:
            from app.ml.sentiment.transformer import TransformerSentiment

            candidates["transformer"] = TransformerSentiment()
        except Exception as exc:  # missing packages or no network: record it rather than fail the report
            notes["transformer"] = f"Not evaluated: {type(exc).__name__}: {exc}"[:300]

    models = {}
    for name, model in candidates.items():
        models[name] = {
            "name": model.name,
            "version": model.version,
            "validation": {k: v for k, v in score(model, validation).items() if k != "errors"},
            "test": score(model, test),
        }
    selected = max(models, key=lambda n: models[n]["validation"]["macro_f1"])
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": {"hash": dataset_hash(), "train": len(train), "validation": len(validation), "test": len(test)},
        "preprocessing_version": PREPROCESSING_VERSION,
        "tfidf_c_search": {str(c): round(v, 4) for c, v in c_search.items()},
        "tfidf_selected_c": best_c,
        "selected": selected,
        "models": models,
        "notes": notes,
    }


def render_markdown(result: dict) -> str:
    d = result["dataset"]
    lines = [
        "# Sentiment evaluation",
        "",
        f"Generated {result['generated_at']} by `python -m app.ml.sentiment.evaluate`. Dataset `{d['hash']}`: "
        f"{d['train']} train, {d['validation']} validation, {d['test']} test examples.",
        "",
        "## Results on the held-out test split",
        "",
        "| Model | Version | Macro F1 | Accuracy | Calibration error (ECE) | Validation macro F1 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, m in result["models"].items():
        marker = " (selected)" if name == result["selected"] else ""
        lines.append(
            f"| {name}{marker} | `{m['version']}` | {m['test']['macro_f1']:.2f} | {m['test']['accuracy']:.2f} | "
            f"{m['test']['ece']:.2f} | {m['validation']['macro_f1']:.2f} |"
        )
    for name, note in result["notes"].items():
        lines.append(f"| {name} | – | – | – | – | {note} |")
    lines += ["", f"The selected model is chosen by validation macro F1, never by test results. TF-IDF regularization search on validation: {result['tfidf_c_search']}."]
    for name, m in result["models"].items():
        t = m["test"]
        lines += ["", f"## {name}", "", "| Class | Precision | Recall | F1 | Support |", "| --- | --- | --- | --- | --- |"]
        lines += [f"| {c} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1']:.2f} | {v['support']} |" for c, v in t["per_class"].items()]
        cm = t["confusion_matrix"]["rows_true_cols_pred"]
        lines += ["", "Confusion matrix (rows are true labels, columns predicted):", "", "| | " + " | ".join(LABELS) + " |", "| --- | --- | --- | --- |"]
        lines += [f"| **{label}** | " + " | ".join(str(x) for x in row) + " |" for label, row in zip(LABELS, cm, strict=True)]
        lines += ["", "Accuracy by tag (small groups, read as indicative only): " + ", ".join(f"{tag} {v['accuracy']:.2f} (n={v['n']})" for tag, v in t["by_tag"].items()) + "."]
        if t["flagged_accuracy"] is not None:
            lines.append(f"{t['flagged_share']:.0%} of test predictions carried a quality flag; accuracy on those was {t['flagged_accuracy']:.2f}.")
        if t["errors"]:
            lines += ["", "Errors:", ""]
            lines += [f"- `{e['id']}` \"{e['text']}\": true **{e['true']}**, predicted {e['pred']} ({e['confidence']:.2f}){' flags: ' + ', '.join(e['flags']) if e['flags'] else ''}" for e in t["errors"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transformer", action="store_true", help="Also evaluate the optional transformer candidate")
    args = parser.parse_args()
    result = run(args.transformer)
    EVALUATION_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_markdown(result))
    print(f"Selected {result['selected']}. Wrote {EVALUATION_PATH} and {REPORT_PATH}")


if __name__ == "__main__":
    main()
