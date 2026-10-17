# CSV import format

Upload on the Sources page, or `POST /api/imports/csv` with form fields `file`, `dataset` and optional `timezone`.

| Column | Required | Notes |
| --- | --- | --- |
| `source_record_id` | yes | Stable ID from wherever the data came from. Re-uploading a row with the same ID in the same dataset is counted as a duplicate, not a new mention. |
| `published_at` | yes | ISO 8601, e.g. `2026-09-01T10:00:00Z` or `2026-09-01 15:30:00+05:30`. Times without an offset use the `timezone` field (default UTC). Stored in UTC. Dates before 2000 or more than a day in the future are rejected. |
| `text` | yes | The post or review text. |
| `url` | no | Public link, only if you are allowed to show it. |
| `language` | no | e.g. `en`, `hi`. |
| `likes`, `comments`, `shares`, `views` | no | Whole numbers of 0 or more. Leave blank when unknown: blank is stored as missing, never as zero. |

Any other column is ignored and listed back to you, so personal data such as emails is never stored by accident.

**Dataset name.** Lowercase letters, digits, `-` and `_`, up to 48 characters. Records are stored with source `csv:<dataset>`, so the same IDs in two different datasets are kept apart.

**Errors.** File-level problems (not UTF-8, missing a required column, over 10 MB or 50,000 rows) reject the whole upload. Row-level problems reject only that row; the response lists the first 50 with row numbers, and the run is marked `partial`.

**Licensing.** Only upload data you are allowed to use for this purpose. Note the source and licence in the dataset name or your own records.
