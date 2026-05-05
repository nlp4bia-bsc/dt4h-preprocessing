from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from extractors import extract_text
from models import RecordInput

app = FastAPI(title="DT4H Preprocessing", version="0.1.0")


@app.post("/process_bulk")
async def process_bulk(request: Request):
    body = await request.json()

    if not isinstance(body, dict) or "content" not in body:
        return JSONResponse({"error": "body must be {\"content\": [...]}"}, status_code=422)

    content = body["content"]
    if not isinstance(content, list):
        return JSONResponse({"error": "'content' must be a list"}, status_code=422)

    # Pass 1: validate all records
    failures = []
    records = []
    for i, item in enumerate(content):
        try:
            records.append(RecordInput.model_validate(item))
        except ValidationError as e:
            failures.append({
                "index": i,
                "patient_id": item.get("patient_id") if isinstance(item, dict) else None,
                "detail": e.errors()[0]["msg"],
            })

    if failures:
        return JSONResponse({"error": "Validation failed", "failures": failures}, status_code=422)

    # Pass 2: extract text from all records
    results = []
    for i, record in enumerate(records):
        try:
            text = extract_text(record.text_path)
        except Exception as e:
            failures.append({
                "index": i,
                "patient_id": record.patient_id,
                "detail": str(e),
            })
            continue
        results.append(record.model_dump() | {"text": text})

    if failures:
        return JSONResponse({"error": "Extraction failed", "failures": failures}, status_code=422)

    return JSONResponse({"content": results})
