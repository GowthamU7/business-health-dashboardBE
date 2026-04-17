from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import csv
import io

from app.models import Assumptions, ScoreResponse
from app.parser import parse_financial_text
from app.scoring import calculate_metrics, calculate_health_score
from app.ai_insights import generate_ai_insights
from app.pdf_utils import extract_text_from_pdf_bytes

app = FastAPI(title="Business Health Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_response(raw_text: str, assumptions_payload: dict):
    try:
        parsed_data = parse_financial_text(raw_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parsing failed: {str(e)}")

    assumptions = Assumptions(**assumptions_payload)

    metrics = calculate_metrics(parsed_data, assumptions)
    score, grade, status = calculate_health_score(metrics, parsed_data)
    ai_insights = generate_ai_insights(parsed_data, metrics, score, grade, status)

    rationale = ai_insights.summary

    return ScoreResponse(
        score=score,
        grade=grade,
        rationale=rationale,
        metrics=metrics,
        parsed_data=parsed_data,
        ai_insights=ai_insights,
    )


@app.get("/")
def root():
    return {"message": "Business Health Dashboard API is running"}


@app.post("/analyze", response_model=ScoreResponse)
def analyze_business(payload: dict):
    raw_text = payload.get("raw_text", "")
    assumptions_payload = payload.get("assumptions", {})
    return build_response(raw_text, assumptions_payload)


@app.post("/analyze-file", response_model=ScoreResponse)
async def analyze_file(
    file: UploadFile = File(...),
    growth_rate_adjustment: float = Form(0),
    owner_salary_adjustment: float = Form(0),
    cost_structure_adjustment: float = Form(0),
):
    content = await file.read()
    filename = file.filename.lower()

    raw_text = ""

    if filename.endswith(".csv"):
        decoded = content.decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(decoded))
        rows = [" | ".join(row) for row in reader]
        raw_text = "\n".join(rows)

    elif filename.endswith(".pdf"):
        try:
            raw_text = extract_text_from_pdf_bytes(content)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to read PDF: {str(e)}"
            )

        if not raw_text.strip():
            raise HTTPException(
                status_code=400,
                detail="PDF uploaded, but no readable text was found in the file."
            )

    else:
        raw_text = content.decode("utf-8", errors="ignore")

    assumptions_payload = {
        "growth_rate_adjustment": growth_rate_adjustment,
        "owner_salary_adjustment": owner_salary_adjustment,
        "cost_structure_adjustment": cost_structure_adjustment,
    }

    return build_response(raw_text, assumptions_payload)