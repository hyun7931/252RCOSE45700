# backend/app/rag/router.py
# 질문 라우팅: 규칙(LLM 없음) → LLM 구조화 출력(의도 + 계산기 입력값 1회 추출)

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

INTENTS = ("review", "what_if", "regulation", "lookup", "other")

CUSTOMER_ID_PATTERN = re.compile(r"\bC\d{4}_\d{3}\b", re.IGNORECASE)
LOOKUP_KEYWORDS = re.compile(r"정보|조회|보여|알려|연체|이력|기존\s*대출|프로필|재직|소득|신용\s*점수|자산|직장")
REVIEW_KEYWORDS = re.compile(r"가능|심사|승인|한도|계산|DSR|LTV|\d+\s*(억|천|만)", re.IGNORECASE)


class RouteDecision(BaseModel):
    """LLM 라우터 출력. 금액은 모두 원 단위 정수"""
    intent: Literal["review", "what_if", "regulation", "lookup", "other"] = Field(
        description="review: 특정 고객·조건으로 대출 가능 여부·심사·한도를 계산해 달라는 요청 / "
                    "what_if: 직전 심사 조건에서 일부만 바꾼 후속 질문(금리가 오르면, 기간을 바꾸면, 금액을 바꾸면 등) / "
                    "regulation: 특정 고객 계산이 아닌 일반 기준·규정·상품·약관 질문(상품 최대한도, LTV·DSR 기준, 전결·본부 심사 기준, 등급 기준, 연체 규정, 금리, 수수료, 대상 고객 등) / "
                    "lookup: 고객 ID로 특정 고객의 정보(소득, 재직, 기존 대출, 연체 이력 등)를 조회 / "
                    "other: 인사·잡담·챗봇 기능 소개, 또는 심사 계산과 규정 질문이 한 문장에 함께 있는 경우만")
    search_query: Optional[str] = Field(default=None, description="regulation일 때 규정 검색에 쓸 질의문")
    customer_id: Optional[str] = Field(default=None, description="고객 ID (예: C2025_001)")
    product_type: Optional[Literal["credit", "mortgage", "auto", "policy"]] = Field(
        default=None, description="상품 (credit:직장인신용, mortgage:주택담보, auto:자동차, policy:새희망홀씨)")
    loan_amount: Optional[int] = Field(default=None, description="대출 신청 금액(원). 예: 1억 → 100000000")
    annual_income: Optional[int] = Field(default=None, description="연소득(원). 예: 연봉 6천 → 60000000")
    credit_score: Optional[int] = Field(default=None, description="신용점수")
    current_annual_repayment: Optional[int] = Field(default=None, description="기존 대출 연 상환액(원). '기존 대출 없음'이면 0")
    job_years: Optional[int] = Field(default=None, description="재직 기간의 년 부분")
    job_months: Optional[int] = Field(default=None, description="재직 기간의 개월 부분")
    interest_rate: Optional[float] = Field(default=None, description="연 금리(%)")
    term_years: Optional[int] = Field(default=None, description="대출 기간(년)")
    stress_rate_increase: Optional[float] = Field(default=None, description="금리 상승폭(%p)")
    has_payroll: Optional[bool] = Field(default=None, description="당행 급여이체 여부")
    auto_transfers: Optional[int] = Field(default=None, description="당행 자동이체 건수")
    asset_amount: Optional[int] = Field(default=None, description="보유 자산(원)")
    collateral_value: Optional[int] = Field(default=None, description="담보 주택 가액(원)")
    region: Optional[Literal["speculative", "adjusted", "normal"]] = Field(
        default=None, description="담보 지역 (speculative:투기과열지구, adjusted:조정대상지역, normal:기타 일반지역)")
    is_actual_demand: Optional[bool] = Field(default=None, description="실수요자 여부")
    user_role: Optional[Literal["staff", "manager", "hq"]] = Field(default=None, description="사용자 직급")


ROUTER_INSTRUCTION = """당신은 디디은행 여신 심사 챗봇의 질문 분류기입니다.
마지막 사용자 질문의 의도를 하나 고르고, 심사 계산에 필요한 값을 추출하세요.
- 값은 대화에서 사용자가 실제로 말한 것만 넣고, 말하지 않은 값은 비워두세요. 추정하지 마세요.
- 이전 대화에서 사용자가 말한 고객 조건도 같은 심사에 해당하면 함께 추출하세요.
- 금액은 원 단위 정수로 바꾸세요. (1억 → 100000000, 6천(만 원) → 60000000, 500만 원 → 5000000)
- "최대한도", "몇 등급부터", "얼마를 넘으면", "기준이 뭐야"처럼 일반 기준을 묻는 질문은 regulation입니다. 특정 고객·조건의 계산 요청만 review입니다.
- 심사 요청과 규정 질문이 함께 있으면 other로 분류하세요."""


def rule_route(message):
    """LLM 없이 결정 가능한 경로. 해당 없으면 None"""
    if CUSTOMER_ID_PATTERN.search(message) and LOOKUP_KEYWORDS.search(message) and not REVIEW_KEYWORDS.search(message):
        return "lookup"
    return None


def extract_customer_id(message):
    match = CUSTOMER_ID_PATTERN.search(message)
    return match.group(0).upper() if match else None


def calculator_inputs(decision):
    """RouteDecision → loan_calculator 입력 (비어 있는 값 제외)"""
    data = decision.model_dump(exclude={"intent", "search_query"})
    if data.get("customer_id"):
        data["customer_id"] = data["customer_id"].upper()
    return {k: v for k, v in data.items() if v is not None}


def history_text(chat_history, max_messages=6, max_chars=400):
    """라우터용 최근 대화 요약 (긴 표 답변은 잘라냄)"""
    lines = []
    for msg in chat_history[-max_messages:]:
        if isinstance(msg, dict) and msg.get("content"):
            role = "사용자" if msg.get("role") == "user" else "챗봇"
            lines.append(f"{role}: {msg['content'][:max_chars]}")
    return "\n".join(lines)


def llm_route(llm, message, chat_history):
    """LLM 구조화 출력 1회로 의도 + 입력값 추출"""
    prompt = f"{ROUTER_INSTRUCTION}\n\n[이전 대화]\n{history_text(chat_history) or '(없음)'}\n\n[마지막 사용자 질문]\n{message}"
    return llm.with_structured_output(RouteDecision).invoke(prompt)
