# backend/app/rag/tools.py

from typing import Optional
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import BaseModel, Field
from app.logic.loan_engine import LoanReviewEngine
from app.rag.vector_store import get_retriever

engine = LoanReviewEngine()
retriever = get_retriever()

# 사용자가 말하지 않았을 때 쓰는 기본값 (적용 시 결과의 '적용 조건'에 표시)
DEFAULT_RATE = 5.0           # 연 금리 (%)
DEFAULT_TERM_YEARS = 5       # 대출 기간 (년)
DEFAULT_STRESS_RATE = 2.0    # 스트레스 테스트 금리 상승폭 (%p), 내부심사규정 제5장
DEFAULT_HAS_PAYROLL = False  # 급여이체 여부
DEFAULT_AUTO_TRANSFERS = 0   # 자동이체 건수
DEFAULT_ASSET_AMOUNT = 0     # 보유 자산 (원)

class CalculatorInput(BaseModel):
    annual_income: int = Field(description="연소득 (단위: 원). 예: 50000000")
    credit_score: int = Field(description="NICE 신용점수. 예: 850")
    current_annual_repayment: int = Field(description="기존 대출의 연간 원리금 상환액 (단위: 원). 없으면 0", default=0)
    loan_amount: int = Field(description="신규 대출 신청 금액 (단위: 원)")
    product_type: str = Field(description="상품 종류 (credit:직장인신용, mortgage:주택담보, auto:자동차, policy:새희망홀씨)", default="credit")
    job_years: int = Field(description="재직 기간의 년 부분. 예: 2년 6개월 → 2. 모르면 0", default=0)
    job_months: int = Field(description="재직 기간의 개월 부분. 예: 2년 6개월 → 6, 18개월 → 18. 모르면 0", default=0)
    user_role: str = Field(description="사용자 직급 (staff:행원, manager:지점장, hq:본부심사역)", default="manager")
    interest_rate: Optional[float] = Field(description=f"연 금리 (% 단위). 예: 4.5. 사용자가 말하지 않았으면 비워둘 것 (기본 {DEFAULT_RATE}%)", default=None)
    term_years: Optional[int] = Field(description=f"대출 기간 (년). 사용자가 말하지 않았으면 비워둘 것 (기본 {DEFAULT_TERM_YEARS}년)", default=None)
    stress_rate_increase: Optional[float] = Field(description=f"스트레스 테스트 금리 상승폭 (%p 단위). 예: '금리 3% 오르면' → 3. 말하지 않았으면 비워둘 것 (기본 {DEFAULT_STRESS_RATE}%p)", default=None)
    has_payroll: Optional[bool] = Field(description="당행 급여이체 여부. 모르면 비워둘 것 (기본: 없음)", default=None)
    auto_transfers: Optional[int] = Field(description="당행 자동이체 건수. 모르면 비워둘 것 (기본: 0건)", default=None)
    asset_amount: Optional[int] = Field(description="보유 자산 합계 (부동산+예금, 단위: 원). 모르면 비워둘 것 (기본: 0원)", default=None)
    collateral_value: Optional[int] = Field(description="[주택담보대출 필수] 담보 주택 가액 (단위: 원). 모르면 비워둘 것", default=None)
    region: Optional[str] = Field(description="[주택담보대출 필수] 담보 주택 지역 구분 (speculative:투기과열지구, adjusted:조정대상지역, normal:기타 일반지역). 모르면 비워둘 것", default=None)
    is_actual_demand: Optional[bool] = Field(description="[주택담보대출] 실수요자 요건 충족 여부. 모르면 비워둘 것 (기본: 아님)", default=None)

#Tool1. 심사 계산기
@tool("loan_calculator", args_schema=CalculatorInput)
def loan_calculator(
    annual_income: int, 
    credit_score: int, 
    loan_amount: int, 
    current_annual_repayment: int = 0, 
    product_type: str = "credit", 
    job_years: int = 0,
    job_months: int = 0,
    user_role: str = "manager",
    interest_rate: Optional[float] = None,
    term_years: Optional[int] = None,
    stress_rate_increase: Optional[float] = None,
    has_payroll: Optional[bool] = None,
    auto_transfers: Optional[int] = None,
    asset_amount: Optional[int] = None,
    collateral_value: Optional[int] = None,
    region: Optional[str] = None,
    is_actual_demand: Optional[bool] = None
):
    """
    고객의 재무 정보를 바탕으로 DSR, 내부 등급(CSS), 대출 승인 여부, 전결 권한, 금리 상승 시 DSR을 계산하는 시뮬레이터입니다.
    구체적인 수치 계산(DSR %)이나 '승인/거절' 판단, 금리 상승 시뮬레이션이 필요할 때 반드시 이 도구를 사용하세요.
    """
    if product_type == "mortgage":
        missing = [label for value, label in [(collateral_value, "담보 주택 가액"), (region, "지역 구분(투기과열지구/조정대상지역/일반지역)")] if not value]
        if missing:
            return f"[필수 정보 누락] 주택담보대출 심사에는 {', '.join(missing)}이(가) 필요합니다. 계산하지 말고 사용자에게 먼저 물어보세요."

    assumed = []
    def pick(value, default, label):
        if value is None:
            assumed.append(label)
            return default
        return value

    rate = pick(interest_rate, DEFAULT_RATE, f"금리 {DEFAULT_RATE}%")
    term = pick(term_years, DEFAULT_TERM_YEARS, f"대출 기간 {DEFAULT_TERM_YEARS}년")
    stress = pick(stress_rate_increase, DEFAULT_STRESS_RATE, f"스트레스 금리 상승폭 +{DEFAULT_STRESS_RATE}%p")
    payroll = pick(has_payroll, DEFAULT_HAS_PAYROLL, "급여이체 없음")
    transfers = pick(auto_transfers, DEFAULT_AUTO_TRANSFERS, f"자동이체 {DEFAULT_AUTO_TRANSFERS}건")
    assets = pick(asset_amount, DEFAULT_ASSET_AMOUNT, f"보유 자산 {DEFAULT_ASSET_AMOUNT}원")

    user_data = {
        "annual_income": annual_income,
        "credit_score": credit_score,
        "current_annual_repayment": current_annual_repayment,
        "job_months": job_years * 12 + job_months,
        "has_payroll": payroll,
        "auto_transfers": transfers,
        "asset_amount": assets
    }
    loan_request = {
        "amount": loan_amount,
        "rate": rate / 100,
        "term": term,
        "stress_rate_increase": stress / 100,
        "product_type": product_type
    }
    if product_type == "mortgage":
        # 실수요자 여부는 투기과열지구에서만 LTV에 영향
        actual_demand = pick(is_actual_demand, False, "실수요자 아님") if region == "speculative" else bool(is_actual_demand)
        loan_request.update({
            "collateral_value": collateral_value,
            "region": region,
            "is_actual_demand": actual_demand
        })

    try:
        result = engine.run_simulation(user_data, loan_request, user_role)
        result["applied_conditions"] = {
            "금리": f"{rate}%",
            "대출 기간": f"{term}년",
            "스트레스 금리 상승폭": f"+{stress}%p",
            "급여이체": "있음" if payroll else "없음",
            "자동이체": f"{transfers}건",
            "보유 자산": f"{assets:,}원",
            "기본값 적용 항목": assumed or "없음",
        }
        if product_type == "mortgage":
            result["applied_conditions"]["담보 주택 가액"] = f"{collateral_value:,}원"
        return result
    except Exception as e:
        return f"계산 중 오류 발생: {str(e)}"

#Tool2. 규정 검색기
@tool("regulatory_search")
def regulatory_search(query: str):
    """
    디디은행의 대출 상품 정보, 규정, 약관 등을 검색합니다.
    '직장인 대출 조건이 뭐야?', '중도상환수수료 얼마야?' 같은 질문에 사용하세요.
    """
    docs = retriever.invoke(query)
    
    if not docs:
        return "관련된 규정이나 상품 정보를 찾을 수 없습니다."

    formatted_results = []
    for doc in docs:
        source = doc.metadata.get("source_file", "알수없음")
        content = doc.page_content
        formatted_results.append(f"[출처: {source}]\n{content}")

    return "\n\n---\n\n".join(formatted_results)

tools = [loan_calculator, regulatory_search]