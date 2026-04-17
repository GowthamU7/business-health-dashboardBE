import json
import os
import re
from dotenv import load_dotenv
from openai import OpenAI

from app.models import FinancialData, AIRationale

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


INSIGHTS_SYSTEM_PROMPT = """
You are analyzing a small business financial snapshot for a business health dashboard.

Your job:
- Explain the health score in plain English.
- Be concise, practical, and trustworthy.
- Focus on what is working, what may be risky, and what should be fixed first.
- Do not sound like a consultant report. Sound like a sharp operator.

Rules:
- Return ONLY valid JSON.
- No markdown fences.
- Keep the summary to 2-3 sentences.
- strengths: 2 to 3 bullet items
- risks: 2 to 3 bullet items
- fix_first: 2 to 3 concrete priority actions
- Be conservative. Do not invent unsupported claims.

Return exactly this JSON shape:
{
  "summary": "",
  "strengths": [],
  "risks": [],
  "fix_first": []
}
"""


def extract_json_object(text: str) -> dict:
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError("No valid JSON object found in AI insights response.")


def fallback_insights(
    parsed_data: FinancialData,
    metrics: dict,
    score: int,
    grade: str,
    status: str,
) -> AIRationale:
    strengths = []
    risks = []
    fix_first = []

    if metrics.get("gross_margin", 0) >= 40:
        strengths.append("Gross margin is healthy, which gives the business room to absorb shocks.")
    else:
        risks.append("Gross margin is not especially strong, so profitability may be vulnerable.")

    if metrics.get("ebitda", 0) > 0:
        strengths.append("The business is generating positive EBITDA, which is a strong operating signal.")
    else:
        risks.append("Negative or weak EBITDA suggests the current cost structure needs attention.")

    if metrics.get("yoy_growth", 0) >= 10:
        strengths.append("Revenue growth is solid and suggests healthy demand.")
    else:
        risks.append("Growth is modest, so future resilience may depend on better retention or expansion.")

    if parsed_data.notes:
        note_lower = parsed_data.notes.lower()
        if "lost one major" in note_lower or "contract" in note_lower:
            risks.append("There appears to be customer concentration risk tied to a lost major contract.")
            fix_first.append("Reduce dependency on a small number of large customers or contracts.")

        if "lease" in note_lower:
            risks.append("An upcoming equipment lease may create additional pressure on future cash flow.")
            fix_first.append("Model the lease impact before it hits and update the expense plan.")

    if parsed_data.expenses.misc and parsed_data.expenses.misc > 0:
        fix_first.append("Review miscellaneous expenses first to identify avoidable spend.")

    if not fix_first:
        fix_first.append("Stress-test the current cost structure before committing to new spending.")
        fix_first.append("Track margin and cash flow monthly so risks show up earlier.")

        summary = (
        f"This business currently looks {status.lower()} overall, with a health score of {score}/100 and a grade of {grade}. "
        f"The strongest signals are margin, profitability, and growth, but there are still a few operational risks worth addressing early."
    )

    return AIRationale(
        summary=summary,
        strengths=strengths[:3] or ["The business shows some encouraging fundamentals."],
        risks=risks[:3] or ["No major red flags were provided in the available snapshot, but deeper cash flow data would improve confidence."],
        fix_first=fix_first[:3],
    )


def generate_ai_insights(
    parsed_data: FinancialData,
    metrics: dict,
    score: int,
    grade: str,
    status: str,
) -> AIRationale:
    prompt = f"""
Analyze this business health snapshot and produce concise operator-style insights.

PARSED DATA:
{parsed_data.model_dump_json(indent=2)}

METRICS:
{json.dumps(metrics, indent=2)}

SCORE:
{score}

GRADE:
{grade}

STATUS:
{status}
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": INSIGHTS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content
        parsed = extract_json_object(content)

        return AIRationale(
            summary=parsed.get("summary", "").strip() or f"This business has a health score of {score}/100.",
            strengths=parsed.get("strengths", [])[:3] or ["Healthy operating signals are present."],
            risks=parsed.get("risks", [])[:3] or ["No major risks were identified from the available snapshot."],
            fix_first=parsed.get("fix_first", [])[:3] or ["Review margins and operating expenses first."],
        )
    except Exception:
                return fallback_insights(parsed_data, metrics, score, grade, status)
                