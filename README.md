# DT4H Preprocessing

Text extraction microservice for the DT4H Cogstack-NiFi pipeline. Receives patient record metadata and a file path, extracts plain text from the record, and returns the original payload with a `text` field appended. Output feeds into OpenSearch (Avro) for downstream NER+NEL annotation.

## API

### `POST /process_bulk`

**Request**
```json
{
  "content": [
    {
      "patient_id": "P001",
      "admission_id": "A123",
      "text_path": "/opt/data/notes/P001.txt",
      "...": "any additional metadata fields are passed through unchanged"
    }
  ]
}
```

`contact_id` can be used instead of `admission_id`. Both `patient_id` and one of the two ID fields are required.

**Response `200`**
```json
{
  "content": [
    {
      "patient_id": "P001",
      "admission_id": "A123",
      "text_path": "/opt/data/notes/P001.txt",
      "text": "Extracted plain text content...",
      "...": "..."
    }
  ]
}
```

**Response `422`** — returned if any record fails validation or extraction. The entire batch is rejected.
```json
{
  "error": "Validation failed",
  "failures": [
    { "index": 0, "patient_id": "P001", "detail": "text_path not found: /opt/..." }
  ]
}
```

### Supported formats

| Format | Notes |
|--------|-------|
| `.txt` | Encoding auto-detected |
| `.pdf` | All pages extracted |
| `.docx` | Paragraph text joined |
| `.xml` | All text nodes concatenated |
| `.json` | Reads top-level `text` or `Text` key |

## Running

**Local**
```bash
uv sync
uv run uvicorn main:app --reload --port 5002
```

**Docker**
```bash
docker compose up --build
```

The service joins the external `cogstack-net` network and mounts `/opt` from the host so that `text_path` values from NiFi resolve correctly inside the container.

## Testing & validation

### Automated tests

```bash
uv sync
uv run pytest test_api.py -v
```

Covers: attribute validation, all supported file formats, `.txt` encoding variants (UTF-8, Latin-1, CP1252, UTF-16). All 20 tests should pass in under 1 second.

---

### Manual — start the service first

```bash
uv run uvicorn main:app --reload --port 5002
# or: docker compose up --build
```

---

### curl examples

**Happy path — single record**
```bash
curl -s -X POST http://localhost:5002/process_bulk \
  -H 'Content-Type: application/json' \
  -d '{
    "content": [{
      "patient_id": "P001",
      "admission_id": "A001",
      "text_path": "/absolute/path/to/file.txt"
    }]
  }' | python3 -m json.tool
```
Expected: `200`, response contains `"text": "<extracted content>"`.

---

**Multiple records — batch**
```bash
curl -s -X POST http://localhost:5002/process_bulk \
  -H 'Content-Type: application/json' \
  -d '{
    "content": [
      {"patient_id": "P001", "admission_id": "A001", "text_path": "/path/to/note.pdf"},
      {"patient_id": "P002", "contact_id":  "C099", "text_path": "/path/to/letter.docx"}
    ]
  }' | python3 -m json.tool
```
Expected: `200`, `content` array has both records with `text` added.

---

**Extra metadata fields pass through**
```bash
curl -s -X POST http://localhost:5002/process_bulk \
  -H 'Content-Type: application/json' \
  -d '{
    "content": [{
      "patient_id": "P001",
      "admission_id": "A001",
      "text_path": "/path/to/file.txt",
      "ward": "Cardiology",
      "source_system": "EPR"
    }]
  }' | python3 -m json.tool
```
Expected: `200`, `ward` and `source_system` appear unchanged in the response record.

---

### Validation error cases

**Missing `patient_id`** → `422`
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:5002/process_bulk \
  -H 'Content-Type: application/json' \
  -d '{"content": [{"admission_id": "A001", "text_path": "/path/to/file.txt"}]}'
```

**Neither `admission_id` nor `contact_id`** → `422`
```bash
curl -s -X POST http://localhost:5002/process_bulk \
  -H 'Content-Type: application/json' \
  -d '{"content": [{"patient_id": "P001", "text_path": "/path/to/file.txt"}]}' \
  | python3 -m json.tool
```
Expected body: `{"error": "Validation failed", "failures": [{"index": 0, ...}]}`.

**File does not exist** → `422`
```bash
curl -s -X POST http://localhost:5002/process_bulk \
  -H 'Content-Type: application/json' \
  -d '{"content": [{"patient_id": "P001", "admission_id": "A001", "text_path": "/tmp/ghost.txt"}]}' \
  | python3 -m json.tool
```

**Unsupported format (`.md`, `.csv`, etc.)** → `422`
```bash
curl -s -X POST http://localhost:5002/process_bulk \
  -H 'Content-Type: application/json' \
  -d '{"content": [{"patient_id": "P001", "admission_id": "A001", "text_path": "/path/to/file.csv"}]}' \
  | python3 -m json.tool
```

**One bad record poisons the batch**
```bash
curl -s -X POST http://localhost:5002/process_bulk \
  -H 'Content-Type: application/json' \
  -d '{
    "content": [
      {"patient_id": "P001", "admission_id": "A001", "text_path": "/path/to/good.txt"},
      {"patient_id": "P002", "text_path": "/path/to/also_good.txt"}
    ]
  }' | python3 -m json.tool
```
Expected: `422`. Record 0 is fine but record 1 fails (no ID) — entire batch rejected.

---

### What to verify

| Check | Pass condition |
|-------|---------------|
| `200` response has `content` array | Same length as input |
| Each output record has `"text"` key | Non-empty string |
| Extra fields preserved | Exact values match input |
| `422` body has `"failures"` array | `index` field matches the bad record position |
| Batch with one bad record returns `422` | No partial success |

## Known limitations

- `.xml`: extracts all text nodes generically — element-specific extraction (e.g. HL7/CDA) pending stakeholder feedback
- `.json`: only reads top-level `text`/`Text` — nested structures not yet supported
- Encoding values `"No encoding"` / `"Unknown"` handled best-effort via charset-normalizer; edge cases not validated
