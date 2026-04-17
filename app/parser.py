import json
import os
import re
from dotenv import load_dotenv
from openai import OpenAI

from app.models import FinancialData

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


PARSER_SYSTEM_PROMPT = """
You extract structured business financial data from messy user-provided financial text.

Rules:
- Return ONLY valid JSON.
- Do not include markdown fences.
- If a value is missing, use 0 for numeric fields and "" for notes.
- Convert dollar values to plain numbers.
- Convert percentages to plain numbers without the % sign.
- Infer fields conservatively. Do not invent data.
- If a field is approximate (for example "~546,000"), still return the numeric estimate.
- For employee counts, map FT/full-time to employees_full_time and seasonal to employees_seasonal.

Return this exact JSON shape:
{
  "business_name": "",
  "year": "",
  "revenue": 0,
  "cogs": 0,
  "gross_profit": 0,
  "operating_expenses": 0,
  "ebitda": 0,
  "owner_sde": 0,
  "yoy_growth": 0,
  "employees_full_time": 0,
  "employees_seasonal": 0,
  "notes": "",
  "expenses": {
    "owner_salary": 0,
    "rent": 0,
    "marketing": 0,
    "misc": 0
  }
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

    raise ValueError("No valid JSON object found in model response.")


def normalize_financial_data(data: dict) -> dict:
    default = {
        "business_name": "Unknown Business",
        "year": "Unknown",
        "revenue": 0,
        "cogs": 0,
        "gross_profit": 0,
        "operating_expenses": 0,
        "ebitda": 0,
        "owner_sde": 0,
        "yoy_growth": 0,
        "employees_full_time": 0,
        "employees_seasonal": 0,
        "notes": "",
        "expenses": {
            "owner_salary": 0,
            "rent": 0,
            "marketing": 0,
            "misc": 0,
        },
    }

    merged = {**default, **(data or {})}
    merged["expenses"] = {**default["expenses"], **((data or {}).get("expenses") or {})}
    return merged


def money_after_label(raw_text: str, label_patterns: list[str]) -> float:
    for pattern in label_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            value = match.group(1)
            cleaned = re.sub(r"[^\d.\-]", "", value)
            try:
                return float(cleaned)
            except ValueError:
                continue
    return 0


def percent_after_label(raw_text: str, label_patterns: list[str]) -> float:
    for pattern in label_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            value = match.group(1)
            cleaned = re.sub(r"[^\d.\-]", "", value)
            try:
                return float(cleaned)
            except ValueError:
                continue
    return 0


def fallback_parse(raw_text: str) -> FinancialData:
    business_match = re.search(r"Business:\s*(.+)", raw_text, re.IGNORECASE)
    year_match = re.search(r"(FY\s*\d{4}|\b20\d{2}\b)", raw_text, re.IGNORECASE)

    ft_match = re.search(r"(\d+)\s*(?:FT|full[\s-]?time)", raw_text, re.IGNORECASE)
    seasonal_match = re.search(r"(\d+)\s*seasonal", raw_text, re.IGNORECASE)

    data = {
        "business_name": business_match.group(1).strip() if business_match else "Unknown Business",
        "year": year_match.group(1).strip() if year_match else "Unknown",
        "revenue": money_after_label(raw_text, [r"Revenue:\s*([~$,\d.\-+]+)"]),
        "cogs": money_after_label(raw_text, [r"COGS.*?:\s*([~$,\d.\-+]+)"]),
        "gross_profit": money_after_label(raw_text, [r"Gross Profit:\s*([~$,\d.\-+]+)"]),
        "operating_expenses": money_after_label(raw_text, [r"Operating Expenses:\s*([~$,\d.\-+]+)"]),
        "ebitda": money_after_label(raw_text, [r"EBITDA:\s*([~$,\d.\-+]+)"]),
        "owner_sde": money_after_label(raw_text, [r"Owner SDE:\s*([~$,\d.\-+]+)"]),
        "yoy_growth": percent_after_label(raw_text, [r"YoY.*?Growth:\s*([~$,\d.\-+%]+)"]),
        "employees_full_time": int(ft_match.group(1)) if ft_match else 0,
        "employees_seasonal": int(seasonal_match.group(1)) if seasonal_match else 0,
        "notes": "",
        "expenses": {
            "owner_salary": money_after_label(raw_text, [r"Owner salary:\s*([~$,\d.\-+]+)"]),
            "rent": money_after_label(raw_text, [r"Rent:\s*([~$,\d.\-+]+)"]),
            "marketing": money_after_label(raw_text, [r"Marketing:\s*([~$,\d.\-+]+)"]),
            "misc": money_after_label(raw_text, [r"Misc:\s*([~$,\d.\-+]+)"]),
        },
    }

    notes_match = re.search(r"Notes:\s*(.+)", raw_text, re.IGNORECASE)
    if notes_match:
        data["notes"] = notes_match.group(1).strip()

    return FinancialData(**normalize_financial_data(data))


def parse_financial_text(raw_text: str) -> FinancialData:
    if not raw_text or not raw_text.strip():
        raise ValueError("No input text provided for parsing.")

    user_prompt = f"""
Extract structured financial data from the following business financial input.

INPUT:
{raw_text}
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": PARSER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        parsed_dict = extract_json_object(content)
        normalized = normalize_financial_data(parsed_dict)
        return FinancialData(**normalized)
    except Exception:
        return fallback_parse(raw_text)