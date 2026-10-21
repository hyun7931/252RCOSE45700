# backend/app/rag/form.py
# 심사 입력 폼: 계산기의 필수 정보 누락 응답 형식과 폼 정보 생성 (LLM·DB 없이 테스트 가능)

# 필수 입력 누락 시 loan_calculator가 돌려주는 표시
MISSING_MARKER = "[필수 정보 누락]"
MISSING_CODES_PREFIX = "누락 항목:"
REQUIRED_FIELD_LABELS = {
    "loan_amount": "대출 신청 금액",
    "annual_income": "연소득",
    "credit_score": "신용점수",
    "current_annual_repayment": "기존 대출 연 상환액",
    "job_tenure": "재직 기간",
    "collateral_value": "담보 주택 가액",
    "region": "지역 구분(투기과열지구/조정대상지역/일반지역)",
}


def missing_message(missing):
    """계산기용 누락 안내 (에이전트가 읽음). 마지막 줄의 코드로 입력 폼을 만듦"""
    labels = ", ".join(REQUIRED_FIELD_LABELS[code] for code in missing)
    return (f"{MISSING_MARKER} 심사에는 {labels}이(가) 필요합니다. 계산하지 말고 사용자에게 먼저 물어보세요. "
            f"(화면에 입력 폼이 함께 표시됩니다)\n{MISSING_CODES_PREFIX} {','.join(missing)}")


def build_form(observation, inputs):
    """loan_calculator의 [필수 정보 누락] 응답 → 입력 폼 정보. 해당 없으면 None"""
    if not isinstance(observation, str) or not observation.startswith(MISSING_MARKER):
        return None
    missing = []
    for line in observation.splitlines():
        if line.startswith(MISSING_CODES_PREFIX):
            missing = [code.strip() for code in line[len(MISSING_CODES_PREFIX):].split(",") if code.strip()]
    prefilled = {k: v for k, v in (inputs or {}).items() if v is not None}
    return {"missing": missing, "prefilled": prefilled}


def form_prompt(missing):
    """폼 제출 후에도 빠진 항목이 있을 때 사용자에게 보일 안내"""
    labels = ", ".join(REQUIRED_FIELD_LABELS.get(code, code) for code in missing)
    return f"심사에 필요한 정보가 빠졌습니다. 아래 입력 폼에서 **{labels}**을(를) 채워 주세요."
