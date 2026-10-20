# backend/tests/test_loan_engine.py
# 실행: backend/ 에서 python -m pytest

import pytest
from app.logic.loan_engine import LoanReviewEngine


@pytest.fixture
def engine():
    return LoanReviewEngine()


def make_user(**overrides):
    user = {
        "annual_income": 100000000,
        "credit_score": 900,
        "current_annual_repayment": 0,
        "job_months": 48,
        "has_payroll": True,
        "auto_transfers": 3,
        "asset_amount": 500000000,
    }
    user.update(overrides)
    return user


MORTGAGE = {"product_type": "mortgage", "collateral_value": 1000000000, "region": "normal"}


def make_request(**overrides):
    req = {"amount": 30000000, "rate": 0.05, "term": 5, "stress_rate_increase": 0.02, "product_type": "credit"}
    req.update(overrides)
    return req


# --- 제2장: CSS ---

def test_css_full_score(engine):
    css = engine.calculate_css_score(1000, 100000000, True, 3, 500000000)
    assert css["total_score"] == 100
    assert css["grade"] == 1
    assert css["grade_band"] == "우량"


def test_css_asset_stability_capped_at_10(engine):
    css = engine.calculate_css_score(0, 0, False, 0, 2000000000)
    assert css["total_score"] == 10


@pytest.mark.parametrize("score,grade", [
    (90, 1), (89.9, 2), (85, 2), (70, 5), (65, 6), (60, 7), (45, 10), (40, 11), (25, 14), (24.9, 15), (0, 15),
])
def test_grade_cutoffs(engine, score, grade):
    assert engine.score_to_grade(score) == grade


@pytest.mark.parametrize("grade,band", [(1, "우량"), (4, "우량"), (5, "일반"), (7, "일반"), (8, "주의"), (10, "주의"), (11, "위험"), (15, "위험")])
def test_grade_band(engine, grade, band):
    assert engine.grade_band(grade) == band


# --- DSR / 한도 ---

def test_dsr_zero_rate(engine):
    assert engine.calculate_dsr(60000000, 0, 60000000, 0, 5) == 0.2


def test_max_loan_within_dsr_hits_limit(engine):
    amount = engine.max_loan_within_dsr(60000000, 10000000, 0.05, 5, 0.40)
    assert engine.calculate_dsr(60000000, 10000000, amount, 0.05, 5) <= 0.40
    assert engine.calculate_dsr(60000000, 10000000, amount + 100000, 0.05, 5) > 0.40


def test_max_loan_within_dsr_no_capacity(engine):
    assert engine.max_loan_within_dsr(30000000, 20000000, 0.05, 5, 0.40) == 0


def test_credit_limit_income_multiple(engine):
    # DSR 여유가 충분하면 연소득 150%와 1.5억 중 작은 값
    assert engine.calculate_credit_limit(80000000, 0, 0.05, 10, 1) == 120000000
    assert engine.calculate_credit_limit(200000000, 0, 0.05, 10, 1) == 150000000
    # 5등급 이하는 연소득 100%
    assert engine.calculate_credit_limit(80000000, 0, 0.05, 10, 5) == 80000000


# --- 제3장 1항: 직장인대출 컷오프 ---

def test_credit_job_months_cutoff(engine):
    auth = engine.determine_approval_authority(30000000, 1, 0.1, "credit", job_months=23, credit_limit=100000000)
    assert auth["level"] == 99
    assert "재직기간" in auth["type"]


def test_credit_grade_9_rejected(engine):
    auth = engine.determine_approval_authority(30000000, 9, 0.1, "credit", job_months=48, credit_limit=100000000)
    assert auth["level"] == 99


def test_credit_over_limit_rejected(engine):
    auth = engine.determine_approval_authority(60000000, 1, 0.1, "credit", job_months=48, credit_limit=50000000)
    assert auth["level"] == 99
    assert "한도" in auth["type"]


# --- 제4장: 전결 ---

def test_auto_approval(engine):
    auth = engine.determine_approval_authority(50000000, 3, 0.30, "mortgage")
    assert auth["level"] == 0


def test_branch_manager(engine):
    auth = engine.determine_approval_authority(150000000, 6, 0.35, "mortgage")
    assert auth["level"] == 1


@pytest.mark.parametrize("amount,grade,dsr,product", [
    (250000000, 2, 0.30, "mortgage"),   # 2억 초과
    (100000000, 2, 0.45, "mortgage"),   # DSR 40~50%
    (100000000, 7, 0.30, "mortgage"),   # 7~10등급
    (10000000, 2, 0.75, "policy"),      # 새희망홀씨 DSR 70% 초과
])
def test_hq_review(engine, amount, grade, dsr, product):
    assert engine.determine_approval_authority(amount, grade, dsr, product)["level"] == 2


def test_policy_dsr_exception_within_70(engine):
    # 새희망홀씨는 DSR 70% 이내면 일반 전결 기준
    assert engine.determine_approval_authority(10000000, 6, 0.65, "policy")["level"] == 1


def test_policy_grade_10_allowed(engine):
    assert engine.determine_approval_authority(10000000, 10, 0.30, "policy")["level"] == 2


@pytest.mark.parametrize("grade,dsr,product", [
    (11, 0.30, "mortgage"),   # 위험 구간
    (11, 0.30, "policy"),     # 새희망홀씨도 11등급 이상은 거절
    (2, 0.51, "mortgage"),    # DSR 50% 초과
])
def test_reject(engine, grade, dsr, product):
    assert engine.determine_approval_authority(100000000, grade, dsr, product)["level"] == 99


def test_check_user_authority(engine):
    hq = {"level": 2, "type": "본부 심사 필수"}
    assert "권한 부족" in engine.check_user_authority(hq, "manager")
    assert "승인 가능" in engine.check_user_authority(hq, "hq")
    assert "System Reject" in engine.check_user_authority({"level": 99, "type": "거절"}, "hq")


# --- 제5장 / 통합 ---

def test_stress_risk_uses_50_percent(engine):
    # 연소득 6천, 기존 상환 1천 / 신규 4천만 → 스트레스 DSR 약 33%, 1억 → 약 56%
    result = engine.run_simulation(make_user(annual_income=60000000, current_annual_repayment=10000000),
                                   make_request(amount=40000000, **MORTGAGE))
    assert result["dsr"]["stress"] < 50
    assert result["risk_analysis"] == "금리 변동 리스크 안정적"

    result = engine.run_simulation(make_user(annual_income=60000000, current_annual_repayment=10000000),
                                   make_request(amount=100000000, **MORTGAGE))
    assert result["dsr"]["stress"] > 50
    assert "50%" in result["risk_analysis"]


def test_run_simulation_credit_includes_limit(engine):
    result = engine.run_simulation(make_user(), make_request())
    assert result["css"]["grade"] == 1
    assert result["credit_limit"] == 150000000
    assert "자동 승인" in result["required_authority"]


def test_run_simulation_non_credit_has_no_limit(engine):
    result = engine.run_simulation(make_user(), make_request(**MORTGAGE))
    assert "credit_limit" not in result


# --- 제3장 2항: 주택담보대출 LTV ---

@pytest.mark.parametrize("region,actual_demand,limit", [
    ("speculative", False, 40), ("speculative", True, 50),
    ("adjusted", False, 50), ("adjusted", True, 50),
    ("normal", False, 70),
])
def test_ltv_limits_by_region(engine, region, actual_demand, limit):
    ltv = engine.calculate_ltv(100000000, 500000000, region, actual_demand)
    assert ltv["limit"] == limit
    assert ltv["ratio"] == 20
    assert ltv["max_loan"] == 500000000 * limit // 100


def test_ltv_max_loan_no_float_error(engine):
    assert engine.calculate_ltv(400000000, 700000000, "normal")["max_loan"] == 490000000


def test_ltv_invalid_inputs(engine):
    with pytest.raises(ValueError):
        engine.calculate_ltv(100000000, 500000000, "seoul")
    with pytest.raises(ValueError):
        engine.calculate_ltv(100000000, 0, "normal")


def test_ltv_over_limit_rejected(engine):
    # 투기과열 40%: 담보 5억 → 한도 2억, 2.5억 신청은 거절
    result = engine.run_simulation(make_user(), make_request(amount=250000000, term=30, product_type="mortgage",
                                                             collateral_value=500000000, region="speculative"))
    assert result["ltv"]["ratio"] == 50
    assert "LTV 40% 한도" in result["required_authority"]


def test_ltv_actual_demand_within_limit(engine):
    # 투기과열 실수요자 50%: 같은 2.5억 신청이 한도 내 → 2억 초과로 본부 심사
    result = engine.run_simulation(make_user(), make_request(amount=250000000, term=30, product_type="mortgage",
                                                             collateral_value=500000000, region="speculative",
                                                             is_actual_demand=True))
    assert result["ltv"]["limit"] == 50
    assert result["required_authority"] == "본부 심사 필수 (2억 초과)"


def test_mortgage_requires_collateral(engine):
    with pytest.raises(ValueError):
        engine.run_simulation(make_user(), make_request(product_type="mortgage"))


def test_non_mortgage_has_no_ltv(engine):
    assert "ltv" not in engine.run_simulation(make_user(), make_request())
