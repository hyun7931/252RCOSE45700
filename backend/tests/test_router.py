# backend/tests/test_router.py
# 규칙 라우터·입력값 정리·고객 조회 표 테스트 (LLM·DB 불필요)

import pytest

from app.rag.router import rule_route, extract_customer_id, calculator_inputs, history_text, merge_inputs, RouteDecision
from app.rag.result_summary import render_customer


@pytest.mark.parametrize("message,expected", [
    ("C2025_008 고객 정보랑 연체 이력 보여줘", "lookup"),
    ("c2025_001 기존 대출 조회해줘", "lookup"),
    ("C2025_001 고객 신용대출 1억 가능해?", None),       # 심사 요청은 LLM 라우터로
    ("C2025_004 고객 한도 얼마야?", None),
    ("고객 정보 보여줘", None),                          # 고객 ID 없음
    ("디디 직장인대출 최대한도 알려줘", None),
])
def test_rule_route(message, expected):
    assert rule_route(message) == expected


def test_extract_customer_id():
    assert extract_customer_id("c2025_008 정보") == "C2025_008"
    assert extract_customer_id("고객 정보") is None


def test_calculator_inputs_drops_empty_and_route_fields():
    decision = RouteDecision(intent="review", search_query="무시", customer_id="c2025_001",
                             loan_amount=100000000, interest_rate=5.0)
    assert calculator_inputs(decision) == {"customer_id": "C2025_001", "loan_amount": 100000000, "interest_rate": 5.0}


def test_history_text_truncates_and_limits():
    history = [{"role": "user", "content": "질문"}, {"role": "assistant", "content": "가" * 1000}]
    text = history_text(history, max_chars=10)
    assert text == "사용자: 질문\n챗봇: " + "가" * 10
    assert history_text([{"role": "user", "content": str(i)} for i in range(10)], max_messages=2) == "사용자: 8\n사용자: 9"


def test_render_customer():
    profile = {
        "customer_id": "C2025_008", "name": "김서윤", "company_name": "유니온", "job_months": 62,
        "annual_income": 126050000, "credit_score": 651, "asset_amount": 192030000,
        "has_payroll": True, "auto_transfers": 4, "current_annual_repayment": 2763252,
        "loans": [{"loan_id": "L_008_1", "product_name": "직장인신용대출", "balance": 15300000,
                   "interest_rate": 3.91, "remaining_months": 75, "annual_repayment": 2763252}],
        "unresolved_delinquency": {"count": 1, "amount": 540000},
    }
    text = render_customer(profile)
    assert "김서윤 (C2025_008)" in text
    assert "재직 5년 2개월" in text
    assert "⚠️ 1건" in text
    assert "| L_008_1 | 직장인신용대출 | 15,300,000원 | 3.91% | 75개월 | 2,763,252원 |" in text


# --- 후속 질문 조건 병합 (#18) ---

LAST = {"customer_id": "C2025_004", "product_type": "mortgage", "loan_amount": 400000000,
        "interest_rate": 4.0, "term_years": 30, "collateral_value": 800000000, "region": "normal"}


def test_merge_overrides_only_new_values():
    merged = merge_inputs(LAST, {"stress_rate_increase": 3.0})
    assert merged == {**LAST, "stress_rate_increase": 3.0}
    assert merge_inputs(LAST, {"loan_amount": 200000000, "term_years": None})["term_years"] == 30


def test_merge_same_customer_keeps_conditions():
    assert merge_inputs(LAST, {"customer_id": "c2025_004", "loan_amount": 1})["region"] == "normal"


def test_merge_new_customer_drops_previous():
    assert merge_inputs(LAST, {"customer_id": "C2025_001", "loan_amount": 100000000}) == {
        "customer_id": "C2025_001", "loan_amount": 100000000}


def test_merge_without_previous():
    assert merge_inputs(None, {"loan_amount": 1}) == {"loan_amount": 1}
