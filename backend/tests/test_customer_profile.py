# backend/tests/test_customer_profile.py
# 고객 DB 행 → 심사 입력값 변환 테스트 (DB 불필요)

from datetime import date, datetime

from app.logic.customer_profile import months_between, annual_repayment, build_profile

TODAY = date(2026, 10, 21)


def test_months_between():
    assert months_between(date(2023, 4, 21), TODAY) == 42
    assert months_between(date(2023, 4, 22), TODAY) == 41   # 하루 모자라면 한 달 빠짐
    assert months_between(None, TODAY) == 0
    assert months_between(date(2027, 1, 1), TODAY) == 0    # 미래 날짜


def test_annual_repayment():
    # 2천만 원, 연 4.5%, 48개월 원리금 균등
    assert annual_repayment(20000000, 4.5, 48) == 5472837
    assert annual_repayment(12000000, 0, 12) == 12000000
    assert annual_repayment(20000000, 4.5, 0) == 0


def customer(**overrides):
    row = {
        "cust_id": "C2025_001", "name": "김디디", "company_name": "디디전자",
        "annual_income": 80000000, "credit_score": 900, "join_date": datetime(2023, 4, 21),
        "asset_amount": 300000000, "has_payroll": "Y", "auto_transfer_cnt": 3,
    }
    row.update(overrides)
    return row


def test_build_profile_basic():
    loans = [{"loan_id": "L1", "product_name": "직장인신용대출", "balance_amt": 20000000,
              "maturity_date": datetime(2030, 10, 21), "interest_rate": 4.5}]
    profile = build_profile(customer(), loans, [], today=TODAY)
    assert profile["job_months"] == 42
    assert profile["has_payroll"] is True
    assert profile["auto_transfers"] == 3
    assert profile["current_annual_repayment"] == 5472837
    assert profile["loans"][0]["remaining_months"] == 48
    assert profile["unresolved_delinquency"] == {"count": 0, "amount": 0}


def test_build_profile_skips_matured_loans():
    loans = [{"loan_id": "L1", "product_name": "직장인신용대출", "balance_amt": 20000000,
              "maturity_date": datetime(2026, 1, 1), "interest_rate": 4.5}]
    profile = build_profile(customer(), loans, [], today=TODAY)
    assert profile["current_annual_repayment"] == 0
    assert profile["loans"] == []


def test_build_profile_counts_only_unresolved_delinquency():
    delinquencies = [
        {"overdue_amt": 1000000, "is_resolved": "N"},
        {"overdue_amt": 500000, "is_resolved": "N"},
        {"overdue_amt": 9000000, "is_resolved": "Y"},
    ]
    profile = build_profile(customer(has_payroll="N", auto_transfer_cnt=None), [], delinquencies, today=TODAY)
    assert profile["unresolved_delinquency"] == {"count": 2, "amount": 1500000}
    assert profile["has_payroll"] is False
    assert profile["auto_transfers"] == 0
