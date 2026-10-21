# backend/app/logic/customer_profile.py
# 고객 DB 원본 데이터 → 심사 엔진 입력값 변환 (DB 없이 테스트 가능)

from datetime import date


def months_between(start, end):
    """start부터 end까지 꽉 찬 개월 수"""
    if start is None or end < start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def annual_repayment(balance, annual_rate_pct, remaining_months):
    """남은 기간 동안 원리금 균등 상환할 때의 연 상환액"""
    if balance <= 0 or remaining_months <= 0:
        return 0
    r = annual_rate_pct / 100 / 12
    if r == 0:
        monthly = balance / remaining_months
    else:
        monthly = balance * r * (1 + r) ** remaining_months / ((1 + r) ** remaining_months - 1)
    return int(round(monthly * 12))


def build_profile(customer, loans, delinquencies, today=None):
    """
    customer: CUSTOMERS 한 행 (dict, 컬럼명 소문자)
    loans: LOAN_ACCOUNTS 행 목록
    delinquencies: DELINQUENCY_HISTORY 행 목록
    """
    today = today or date.today()

    loan_items = []
    total_repayment = 0
    for loan in loans:
        maturity = _to_date(loan["maturity_date"])
        remaining = months_between(today, maturity)
        if remaining <= 0:
            continue  # 만기 지난 대출은 상환 부담에서 제외
        yearly = annual_repayment(loan["balance_amt"], float(loan["interest_rate"]), remaining)
        total_repayment += yearly
        loan_items.append({
            "loan_id": loan["loan_id"],
            "product_name": loan["product_name"],
            "balance": int(loan["balance_amt"]),
            "interest_rate": float(loan["interest_rate"]),
            "remaining_months": remaining,
            "annual_repayment": yearly,
        })

    unresolved = [d for d in delinquencies if d["is_resolved"] != "Y"]

    return {
        "customer_id": customer["cust_id"],
        "name": customer["name"],
        "company_name": customer.get("company_name"),
        "annual_income": int(customer["annual_income"]),
        "credit_score": int(customer["credit_score"]),
        "job_months": months_between(_to_date(customer.get("join_date")), today),
        "asset_amount": int(customer.get("asset_amount") or 0),
        "has_payroll": customer.get("has_payroll") == "Y",
        "auto_transfers": int(customer.get("auto_transfer_cnt") or 0),
        "current_annual_repayment": total_repayment,
        "loans": loan_items,
        "unresolved_delinquency": {
            "count": len(unresolved),
            "amount": int(sum(d["overdue_amt"] for d in unresolved)),
        },
    }


def _to_date(value):
    # oracledb는 DATE를 datetime으로 돌려줌
    if value is None:
        return None
    return value.date() if hasattr(value, "date") and callable(value.date) else value
