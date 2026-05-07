# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run dev server
uv run uvicorn main:app --reload --port 5002

# Add dependency
uv add <package>

# Sync environment
uv sync

# Docker
docker compose up --build

# Generate test records from a directory of .txt files
uv run python create_test_records.py [--source DIR] [--records DIR] [--ptrs DIR] [--font TTF]
```

## Architecture

Preprocessing microservice in a Cogstack-NiFi pipeline. Receives patient record metadata + a file path, extracts plain text, returns the same payload with a `text` field added. Output is consumed by OpenSearch (Avro). Runs on the `cogstack-net` docker network alongside NiFi.

**Endpoint:** `POST /process`

Input: flat JSON per flowfile (NiFi sends one flowfile at a time):
```json
{ "patient_id": "...", "admission_id|contact_id": "...", "text_path": "/opt/...", ...extras }
```

Output: same object with `text` field added.

**Validation (hard fail):**
- `patient_id` required
- `admission_id` OR `contact_id` required (at least one)
- `text_path` must exist on filesystem
- Extra fields pass through unchanged (`model_config = ConfigDict(extra='allow')`)

**Text extraction by format** (`main.py` — `_extract_*` functions):
| Format | Library | Notes |
|--------|---------|-------|
| `.txt` | charset-normalizer | encoding auto-detected |
| `.pdf` | pdfplumber | all pages joined |
| `.docx` | python-docx | non-empty paragraphs joined |
| `.xml` | stdlib `xml.etree.ElementTree` | all text nodes via `itertext()` |
| `.json` | stdlib json | reads `data['text']` or `data['Text']` |

**Error strategy:** validate first, then extract. On failure: `{"error": "...", "detail": "..."}` with 422.

## Code structure

All logic lives in `main.py` — no separate module files. Three sections separated by header comments:
- `# ── Models ──` — Pydantic `RecordInput`
- `# ── Text extraction ──` — `extract_text()` dispatcher + `_extract_*` helpers
- `# ── API ──` — FastAPI app and `/process` endpoint

## Testing

```bash
uv run pytest test_api.py -v
```

Tests use FastAPI `TestClient` (in-process, no server needed). Sample files in `parsing_test_files/` — real Spanish medical records, gitignored. Generate them with `create_test_records.py` if missing.

Content-specific assertions (e.g. `assert "NOTAS EXPLICATIVAS" in text`) are tied to the actual content of the sample files. If sample files are replaced, update those assertions to match.

## Future work

- `.xml`: currently extracts all text nodes generically — stakeholder feedback needed for element-specific extraction (HL7/CDA structure)
- `.json`: currently only reads top-level `text`/`Text` key — stakeholder feedback needed for nested structures
- Encoding `"No encoding"` / `"Unknown"`: charset-normalizer handles best-effort detection; edge cases not yet validated
