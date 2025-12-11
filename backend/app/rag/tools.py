# backend/app/rag/tools.py

from langchain_core.tools import tool
from langchain_core.pydantic_v1 import BaseModel, Field
from app.logic.loan_engine import LoanReviewEngine
from app.rag.vector_store import get_retriever

engine = LoanReviewEngine()
retriever = get_retriever()

class CalculatorInput(BaseModel):
    annual_income: int = Field(description="연소득 (단위: 원). 예: 50000000")
    credit_score: int = Field(description="NICE 신용점수. 예: 850")
    current_annual_repayment: int = Field(description="기존 대출의 연간 원리금 상환액 (단위: 원). 없으면 0", default=0)
    loan_amount: int = Field(description="신규 대출 신청 금액 (단위: 원)")
    product_type: str = Field(description="상품 종류 (credit:직장인신용, mortgage:주택담보, auto:자동차, policy:새희망홀씨)", default="credit")
    job_years: int = Field(description="재직 기간 (년 단위). 모르면 0", default=0)
    user_role: str = Field(description="사용자 직급 (staff:행원, manager:지점장, hq:본부심사역)", default="manager")

#Tool1. 심사 계산기
@tool("loan_calculator", args_schema=CalculatorInput)
def loan_calculator(
    annual_income: int, 
    credit_score: int, 
    loan_amount: int, 
    current_annual_repayment: int = 0, 
    product_type: str = "credit", 
    job_years: int = 0,
    user_role: str = "manager"
):
    """
    고객의 재무 정보를 바탕으로 DSR, 내부 등급(CSS), 대출 승인 여부, 전결 권한을 계산하는 시뮬레이터입니다.
    구체적인 수치 계산(DSR %)이나 '승인/거절' 판단이 필요할 때 반드시 이 도구를 사용하세요.
    """
    user_data = {
        "annual_income": annual_income,
        "credit_score": credit_score,
        "current_annual_repayment": current_annual_repayment,
        "job_years": job_years,
        "has_payroll": True,
        "auto_transfers": 3
    }
    loan_request = {
        "amount": loan_amount,
        "rate": 0.05,
        "term": 5,
        "product_type": product_type
    }

    try:
        result = engine.run_simulation(user_data, loan_request, user_role)
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