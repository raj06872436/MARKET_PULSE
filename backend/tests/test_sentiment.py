import json

import pytest

from app.db.models import ModelVersion, NlpResult, SocialRecord
from app.ml.sentiment import evaluate
from app.ml.sentiment.dataset import load_labelled
from app.ml.sentiment.lexicon import LexiconSentiment
from app.ml.sentiment.preprocess import preprocess

lexicon = LexiconSentiment()


def label(text: str) -> str:
    return lexicon.predict([text])[0].label


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The camera is amazing", "positive"),
        ("Battery is terrible", "negative"),
        ("Not bad at all", "positive"),
        ("Not good", "negative"),
        ("Camera is great but the battery is terrible", "negative"),
        ("Battery is terrible but the camera is great", "positive"),
        ("Display is beautiful though it heats up a little", "positive"),
        ("Phone arrived on Tuesday", "neutral"),
        ("Love it ❤️", "positive"),
        ("Waste of money 😡", "negative"),
        ("Mast phone hai, camera badhiya", "positive"),
        ("Bekaar phone, bahut garam hota hai", "negative"),
        ("Oh great, another update that kills my battery", "negative"),
    ],
)
def test_lexicon_rules(text, expected):
    assert label(text) == expected


def test_quality_flags():
    mixed = lexicon.predict(["Great camera, terrible battery"])[0]
    assert "mixed" in mixed.flags
    sarcastic = lexicon.predict(["Oh great, another update that kills my battery"])[0]
    assert "sarcasm_cue" in sarcastic.flags
    nothing = lexicon.predict(["Phone weighs 190 grams"])[0]
    assert "low_signal" in nothing.flags
    assert "unsupported_script" in lexicon.predict(["रेडमी नोट 14"])[0].flags
    assert abs(sum(nothing.scores.values()) - 1) < 0.01


def test_preprocess_strips_urls_mentions_and_repeats():
    assert preprocess("Sooooo good @alice https://x.y/z #RedmiNote14") == "soo good @user redminote14"


def test_labelled_splits_do_not_leak():
    data = load_labelled()
    by_split = {s: {e.text.casefold() for e in data if e.split == s} for s in ("train", "validation", "test")}
    assert not by_split["train"] & by_split["test"]
    assert not by_split["validation"] & by_split["test"]
    assert len(by_split["test"]) >= 30
    assert {e.label for e in data} == {"positive", "neutral", "negative"}


def test_committed_evaluation_matches_a_fresh_run():
    """evaluation.json drives model selection, so it must be regenerated when models or data change."""
    committed = json.loads(evaluate.EVALUATION_PATH.read_text())
    fresh = evaluate.run()
    assert committed["dataset"] == fresh["dataset"]
    assert committed["selected"] == fresh["selected"]
    for name, model in fresh["models"].items():
        assert committed["models"][name]["version"] == model["version"]
        assert committed["models"][name]["test"]["macro_f1"] == model["test"]["macro_f1"]


CSV = (
    "source_record_id,published_at,text\n"
    "a,2026-09-01T00:00:00Z,Camera is amazing\n"
    "b,2026-09-01T00:00:00Z,Battery is terrible\n"
    "c,2026-09-01T00:00:00Z,Phone arrived today\n"
)


def upload(client):
    return client.post("/api/imports/csv", data={"dataset": "s"}, files={"file": ("s.csv", CSV.encode(), "text/csv")})


def test_imported_records_are_scored_once_with_model_version(client, db_session):
    upload(client)
    results = {r.record_id: r for r in db_session.query(NlpResult)}
    records = {r.source_record_id: r.id for r in db_session.query(SocialRecord)}
    assert results[records["a"]].sentiment == "positive"
    assert results[records["b"]].sentiment == "negative"
    assert results[records["c"]].sentiment == "neutral"
    stored = results[records["a"]]
    assert (stored.model_name, stored.model_version, stored.preprocessing_version) == ("lexicon", "lex-2", "pre-1")
    assert stored.scores_json and 0 < stored.confidence <= 1

    upload(client)
    assert db_session.query(NlpResult).count() == 3

    model = db_session.query(ModelVersion).one()
    assert (model.task, model.status) == ("sentiment", "active")
    assert model.evaluation_json["test"]["macro_f1"] > 0


def test_backfill_endpoint_scores_only_pending(client, db_session):
    upload(client)
    db_session.query(NlpResult).filter(NlpResult.record_id.in_(db_session.query(SocialRecord.id).limit(1))).delete(synchronize_session=False)
    db_session.commit()
    first = client.post("/api/analysis/sentiment").json()
    assert first["scored"] == 1
    assert first["model"]["name"] == "lexicon"
    assert client.post("/api/analysis/sentiment").json()["scored"] == 0
    assert [m["status"] for m in client.get("/api/models").json()] == ["active"]
