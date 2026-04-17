from app.models import FinancialData, Assumptions


def calculate_metrics(data: FinancialData, assumptions: Assumptions):
    revenue = data.revenue * (1 + assumptions.growth_rate_adjustment / 100)

    owner_salary = max(0, data.expenses.owner_salary + assumptions.owner_salary_adjustment)

    operating_expenses = max(
        0,
        data.operating_expenses * (1 + assumptions.cost_structure_adjustment / 100)
    )

    gross_profit = revenue - data.cogs
    gross_margin = ((gross_profit / revenue) * 100) if revenue > 0 else 0
    ebitda = gross_profit - operating_expenses
    ebitda_margin = ((ebitda / revenue) * 100) if revenue > 0 else 0
    owner_sde = ebitda + owner_salary

    expense_ratio = ((operating_expenses / revenue) * 100) if revenue > 0 else 0
    owner_salary_ratio = ((owner_salary / revenue) * 100) if revenue > 0 else 0

    metrics = {
        "revenue": round(revenue, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin": round(gross_margin, 2),
        "operating_expenses": round(operating_expenses, 2),
        "expense_ratio": round(expense_ratio, 2),
        "ebitda": round(ebitda, 2),
        "ebitda_margin": round(ebitda_margin, 2),
        "owner_sde": round(owner_sde, 2),
        "owner_salary": round(owner_salary, 2),
        "owner_salary_ratio": round(owner_salary_ratio, 2),
        "yoy_growth": round(data.yoy_growth + assumptions.growth_rate_adjustment, 2),
    }

    return metrics


def calculate_health_score(metrics: dict, parsed_data: FinancialData):
    score = 50

    gross_margin = metrics.get("gross_margin", 0)
    yoy_growth = metrics.get("yoy_growth", 0)
    ebitda_margin = metrics.get("ebitda_margin", 0)
    expense_ratio = metrics.get("expense_ratio", 0)
    owner_salary_ratio = metrics.get("owner_salary_ratio", 0)

    # Gross margin
    if gross_margin >= 45:
        score += 12
    elif gross_margin >= 35:
        score += 8
    elif gross_margin >= 25:
        score += 3
    else:
        score -= 10

    # Growth
    if yoy_growth >= 20:
        score += 10
    elif yoy_growth >= 10:
        score += 7
    elif yoy_growth >= 3:
        score += 2
    elif yoy_growth < 0:
        score -= 10

    # EBITDA margin
    if ebitda_margin >= 20:
        score += 12
    elif ebitda_margin >= 10:
        score += 8
    elif ebitda_margin >= 5:
        score += 3
    else:
        score -= 12

    # Expense pressure
    if expense_ratio > 35:
        score -= 8
    elif expense_ratio > 25:
        score -= 4
    else:
        score += 2

    # Owner dependency
    if owner_salary_ratio > 20:
        score -= 6
    elif owner_salary_ratio > 10:
        score -= 2
    else:
        score += 2

    # Notes-based risk adjustments
    notes = (parsed_data.notes or "").lower()

    if "lost" in notes and "contract" in notes:
        score -= 8

    if "lease" in notes:
        score -= 4

    if "seasonal" in notes:
        score -= 2

    score = max(0, min(100, round(score)))

    if score >= 85:
        grade = "A"
        status = "Strong"
    elif score >= 70:
        grade = "B"
        status = "Stable"
    elif score >= 55:
        grade = "C"
        status = "Watchlist"
    else:
        grade = "D"
        status = "At Risk"

    return score, grade, status