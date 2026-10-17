# Model card: sentiment

## What it does

Labels each stored post as **positive**, **neutral** or **negative**, with a confidence and quality flags. Results are stored in `nlp_results` with the model name, model version and preprocessing version, so every label can be traced to the exact model that produced it. The active model and its evaluation are recorded in `model_versions`.

## Models compared

| Model | How it works | Status |
| --- | --- | --- |
| `lexicon` (`lex-2`) | Product-review word list with negation ("not bad"), intensifiers ("very"), contrast ("A but B" weights B), emoji, common Hinglish words, and sarcasm cues | **Active**: best validation macro F1 |
| `tfidf-logreg` | TF-IDF word and character n-grams with logistic regression, trained on the train split | Benchmark only: too little training data |
| `transformer` | Pretrained `cardiffnlp/twitter-xlm-roberta-base-sentiment`, optional | Not yet evaluated: needs `requirements-ml-optional.txt` and access to huggingface.co. Check its licence before use |

The current numbers are in [evaluation/sentiment.md](evaluation/sentiment.md). Regenerate them with `python -m app.ml.sentiment.evaluate` (add `--transformer` to include the transformer). A test fails if the committed results are out of date.

## Evaluation data

`backend/app/ml/sentiment/data/labelled.csv` contains 170 short posts about budget phones: 55 positive, 50 neutral and 65 negative. 34 are held out for testing and 34 for validation. The set deliberately includes sarcasm, mixed opinions, negation, Hinglish, emoji, questions and news-style posts. Each row's tags record which.

**These labels were written and assigned by Claude, not by people, and the lexicon was written by the same author.** The test score is therefore optimistic. Before relying on it, have at least two people re-label the test split independently, measure their agreement, and re-run the evaluation. The plan's checklist asks for at least 30 human-checked examples.

## Quality flags

| Flag | Meaning |
| --- | --- |
| `mixed` | Both positive and negative words found |
| `sarcasm_cue` | Phrasing often used ironically ("oh great", "just what I needed") |
| `low_signal` | No sentiment words found; usually labelled neutral |
| `low_confidence` | Top probability under 0.5 |
| `unsupported_script` | Text in a script the lexicon doesn't cover (e.g. Devanagari) |

Dashboards should show the distribution of labels with sample sizes and flag rates, not single-post verdicts.

## Known limitations

- English and romanized Hindi only. Devanagari and other scripts are flagged and mostly scored neutral.
- Sarcasm is caught only for a few common phrasings. Most irony will be missed.
- Product-specific slang outside the word list is invisible to the lexicon.
- Confidence values are rough. The lexicon's calibration error on the test split is about 0.15.
- Sentiment is not purchase intent, and a shift in sentiment does not show a cause.
- No model is trained on collected posts. Platform terms (Reddit's, for example) may forbid that without permission.
