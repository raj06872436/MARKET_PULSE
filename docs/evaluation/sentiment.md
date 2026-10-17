# Sentiment evaluation

Generated 2026-10-17T16:12:24+00:00 by `python -m app.ml.sentiment.evaluate`. Dataset `cef3c926`: 102 train, 34 validation, 34 test examples.

## Results on the held-out test split

| Model | Version | Macro F1 | Accuracy | Calibration error (ECE) | Validation macro F1 |
| --- | --- | --- | --- | --- | --- |
| lexicon (selected) | `lex-2` | 0.88 | 0.88 | 0.15 | 0.85 |
| tfidf-logreg | `tfidf-1-c1-cef3c926` | 0.39 | 0.38 | 0.07 | 0.53 |

The selected model is chosen by validation macro F1, never by test results. TF-IDF regularization search on validation: {'0.5': 0.5032, '1.0': 0.5299, '2.0': 0.5299, '5.0': 0.5299, '10.0': 0.5299}.

## lexicon

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| negative | 0.92 | 0.85 | 0.88 | 13 |
| neutral | 0.90 | 0.90 | 0.90 | 10 |
| positive | 0.83 | 0.91 | 0.87 | 11 |

Confusion matrix (rows are true labels, columns predicted):

| | negative | neutral | positive |
| --- | --- | --- | --- |
| **negative** | 11 | 1 | 1 |
| **neutral** | 0 | 9 | 1 |
| **positive** | 1 | 0 | 10 |

Accuracy by tag (small groups, read as indicative only): emoji 1.00 (n=1), hinglish 1.00 (n=2), mixed 1.00 (n=2), negation 0.50 (n=2), news 1.00 (n=3), plain 0.87 (n=15), question 0.67 (n=3), sarcasm 1.00 (n=2), short 1.00 (n=8).
47% of test predictions carried a quality flag; accuracy on those was 0.88.

Errors:

- `s016` "Never had a single crash in three months": true **positive**, predicted negative (0.84)
- `s066` "Service center kept my phone for 3 weeks and still didn't fix it": true **negative**, predicted neutral (0.53) flags: low_signal
- `s091` "Paid extra for fast delivery and it still took 10 days": true **negative**, predicted positive (0.46) flags: low_confidence
- `s166` "Poll: which brand has the best after-sales service?": true **neutral**, predicted positive (0.92)

## tfidf-logreg

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| negative | 0.36 | 0.38 | 0.37 | 13 |
| neutral | 0.56 | 0.50 | 0.53 | 10 |
| positive | 0.27 | 0.27 | 0.27 | 11 |

Confusion matrix (rows are true labels, columns predicted):

| | negative | neutral | positive |
| --- | --- | --- | --- |
| **negative** | 5 | 2 | 6 |
| **neutral** | 3 | 5 | 2 |
| **positive** | 6 | 2 | 3 |

Accuracy by tag (small groups, read as indicative only): emoji 1.00 (n=1), hinglish 0.00 (n=2), mixed 0.50 (n=2), negation 0.00 (n=2), news 0.67 (n=3), plain 0.33 (n=15), question 0.67 (n=3), sarcasm 0.50 (n=2), short 0.25 (n=8).
76% of test predictions carried a quality flag; accuracy on those was 0.42.

Errors:

- `s001` "Camera on the Redmi Note 14 is honestly amazing for this price": true **positive**, predicted neutral (0.54)
- `s011` "10/10 would recommend to anyone on a budget": true **positive**, predicted neutral (0.42) flags: low_confidence
- `s016` "Never had a single crash in three months": true **positive**, predicted negative (0.43) flags: low_confidence
- `s026` "Gaming performance is smooth, no frame drops in BGMI": true **positive**, predicted negative (0.55)
- `s031` "Highly impressed with the fingerprint sensor speed": true **positive**, predicted negative (0.49) flags: low_confidence
- `s036` "Screen is gorgeous for movies and youtube": true **positive**, predicted negative (0.36) flags: low_confidence
- `s046` "Very satisfied with the purchase overall": true **positive**, predicted negative (0.44) flags: low_confidence
- `s051` "Phone heats up like crazy while gaming": true **negative**, predicted positive (0.38) flags: low_confidence
- `s061` "Not worth the money at all": true **negative**, predicted positive (0.52)
- `s066` "Service center kept my phone for 3 weeks and still didn't fix it": true **negative**, predicted positive (0.52)
- `s071` "Bekaar phone hai, garam bahut hota hai": true **negative**, predicted positive (0.60)
- `s076` "Camera app crashes whenever I switch to video": true **negative**, predicted neutral (0.46) flags: low_confidence
- `s081` "Cheap plastic feel, creaks when you press the back": true **negative**, predicted positive (0.40) flags: low_confidence
- `s096` "Totally overpriced for what you get": true **negative**, predicted positive (0.39) flags: low_confidence
- `s106` "Nothing says flagship like lagging on WhatsApp": true **negative**, predicted neutral (0.40) flags: low_confidence
- `s112` "Battery is terrible but the camera is great": true **positive**, predicted negative (0.41) flags: low_confidence
- `s136` "Kaunsa phone lena chahiye 15k ke andar?": true **neutral**, predicted positive (0.42) flags: low_confidence
- `s146` "Exchange offer valid till Sunday": true **neutral**, predicted negative (0.44) flags: low_confidence
- `s151` "Phone arrived": true **neutral**, predicted positive (0.45) flags: low_confidence
- `s156` "Delivery scheduled for next Tuesday": true **neutral**, predicted negative (0.34) flags: low_confidence
- `s161` "Battery health is at 96% after 6 months": true **neutral**, predicted negative (0.52)
