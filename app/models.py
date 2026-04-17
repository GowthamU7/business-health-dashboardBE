from pydantic import BaseModel, Field
from typing import Optional, List


class ExpenseBreakdown(BaseModel):
    owner_salary: Optional[float] = 0
    rent: Optional[float] = 0
    marketing: Optional[float] = 0
    misc: Optional[float] = 0


class FinancialData(BaseModel):
    business_name: Optional[str] = "Unknown Business"
    year: Optional[str] = "Unknown"
    revenue: Optional[float] = 0
    cogs: Optional[float] = 0
    gross_profit: Optional[float] = 0
    operating_expenses: Optional[float] = 0
    ebitda: Optional[float] = 0
    owner_sde: Optional[float] = 0
    yoy_growth: Optional[float] = 0
    employees_full_time: Optional[int] = 0
    employees_seasonal: Optional[int] = 0
    notes: Optional[str] = ""
    expenses: ExpenseBreakdown = Field(default_factory=ExpenseBreakdown)


class Assumptions(BaseModel):
    growth_rate_adjustment: float = 0
    owner_salary_adjustment: float = 0
    cost_structure_adjustment: float = 0


class AIRationale(BaseModel):
    summary: str
    strengths: List[str]
    risks: List[str]
    fix_first: List[str]


class ScoreResponse(BaseModel):
    score: int
    grade: str
    rationale: str
    metrics: dict
    parsed_data: FinancialData
    ai_insights: AIRationale