from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from extractors import extract_text
from models import RecordInput

app = FastAPI(title="DT4H Preprocessing", version="0.1.0")


@app.post("/process")
async def process(request: Request):
    body = await request.json()

    try:
        record = RecordInput.model_validate(body)
    except ValidationError as e:
        return JSONResponse(
            {"error": "Validation failed", "detail": e.errors()[0]["msg"]},
            status_code=422,
        )

    try:
        text = extract_text(record.text_path)
    except Exception as e:
        return JSONResponse(
            {"error": "Extraction failed", "detail": str(e)},
            status_code=422,
        )

    return JSONResponse(record.model_dump() | {"text": text})
