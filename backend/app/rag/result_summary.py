# backend/app/rag/result_summary.py
# 심사 결과 표는 코드가 렌더링하고, LLM 해설은 판정·수치 모순만 검증 (LLM 없이 테스트 가능)

import re

# 내부심사규정 기준 수치 (해설에서 언급해도 되는 퍼센트)
REGULATION_PERCENTS = {30, 40, 50, 70}

# "대출 가능 여부", "승인 가능성"처럼 단정이 아닌 표현은 제외
AFFIRMATIVE_PATTERN = re.compile(r"(대출|승인|취급|실행)\s*(이|은|는)?\s*가능(?!\s*(여부|성|한지|할지|한가|할까|한 지))")
PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def is_calculation_result(result):
    return isinstance(result, dict) and "css" in result and "dsr" in result


def can_approve(result):
    """사용자 직급으로 승인 가능한 결과인지 (권한 부족·거절이면 False)"""
    return result.get("user_role_check", "").startswith("[승인 가능]")


def _won(amount):
    eok, rest = divmod(int(amount), 100000000)
    man = rest // 10000
    if eok and man:
        short = f"{eok}억 {man:,}만"
    elif eok:
        short = f"{eok}억"
    else:
        short = f"{man:,}만"
    return f"{int(amount):,}원 ({short} 원)"


def render_summary(result):
    """엔진 결과 → 마크다운 표 (숫자·판정은 여기서만 씀)"""
    css, dsr = result["css"], result["dsr"]
    rows = [
        ("판정", result["required_authority"]),
        ("내 권한", result["user_role_check"]),
        ("내부 등급", f"{css['grade']}등급 ({css.get('grade_band', '')}, {css['total_score']}점)"),
        ("DSR", f"{dsr['current']}%"),
        ("스트레스 DSR", f"{dsr['stress']}% (금리 {dsr['stress_rate_increase']}) · {result['risk_analysis']}"),
    ]
    if "credit_limit" in result:
        rows.append(("직장인대출 한도", _won(result["credit_limit"])))
    if "ltv" in result:
        ltv = result["ltv"]
        rows.append(("LTV", f"{ltv['ratio']}% (한도 {ltv['limit']:g}%, {ltv['region']}, 최대 {_won(ltv['max_loan'])})"))

    lines = ["**심사 결과** (내부 심사 엔진 계산)", "", "| 항목 | 결과 |", "|------|------|"]
    lines += [f"| {name} | {value} |" for name, value in rows]

    conditions = result.get("applied_conditions") or {}
    if conditions:
        assumed = conditions.get("기본값 적용 항목")
        shown = [f"{k} {v}" for k, v in conditions.items() if k != "기본값 적용 항목"]
        lines += ["", "**적용 조건**: " + " · ".join(shown)]
        if assumed and assumed != "없음":
            lines.append(f"**기본값 적용**: {', '.join(assumed)} (실제 값을 알려주시면 다시 계산합니다)")
    return "\n".join(lines)


def allowed_percents(result):
    """해설에서 언급해도 되는 퍼센트: 엔진 결과·적용 조건·규정 기준"""
    allowed = set(REGULATION_PERCENTS)
    dsr = result["dsr"]
    allowed |= {float(dsr["current"]), float(dsr["stress"])}
    allowed |= {float(x) for x in re.findall(r"\d+(?:\.\d+)?", dsr.get("stress_rate_increase", ""))}
    if "ltv" in result:
        allowed |= {float(result["ltv"]["ratio"]), float(result["ltv"]["limit"])}
    for value in (result.get("applied_conditions") or {}).values():
        if isinstance(value, str):
            allowed |= {float(x) for x in PERCENT_PATTERN.findall(value)}
            allowed |= {float(x) for x in re.findall(r"\+(\d+(?:\.\d+)?)%p", value)}
    return allowed


def check_commentary(text, result):
    """해설의 문제 목록. 비어 있으면 통과"""
    problems = []
    if not can_approve(result):
        match = AFFIRMATIVE_PATTERN.search(text)
        if match:
            problems.append(f"판정은 '{result['required_authority']}'인데 '{match.group(0)}'처럼 승인을 단정하는 표현이 있습니다.")

    allowed = allowed_percents(result)
    unknown = sorted({p for p in PERCENT_PATTERN.findall(text)
                      if not any(abs(float(p) - a) < 0.01 for a in allowed)}, key=float)
    if unknown:
        problems.append(f"엔진 결과에 없는 수치가 있습니다: {', '.join(p + '%' for p in unknown)}")
    return problems


def render_customer(profile):
    """고객 DB 조회 결과 → 마크다운 (LLM 없이 표시)"""
    months = profile["job_months"]
    lines = [
        f"**고객 정보** {profile['name']} ({profile['customer_id']}) · 고객 DB 조회",
        "",
        "| 항목 | 내용 |",
        "|------|------|",
        f"| 직장 | {profile.get('company_name') or '-'} (재직 {months // 12}년 {months % 12}개월) |",
        f"| 연소득 | {_won(profile['annual_income'])} |",
        f"| 신용점수 | {profile['credit_score']}점 |",
        f"| 보유 자산 | {_won(profile['asset_amount'])} |",
        f"| 당행 거래 | 급여이체 {'있음' if profile['has_payroll'] else '없음'} · 자동이체 {profile['auto_transfers']}건 |",
        f"| 기존 대출 연 상환액 | {_won(profile['current_annual_repayment'])} |",
    ]
    delinquency = profile["unresolved_delinquency"]
    if delinquency["count"]:
        lines.append(f"| 미해결 연체 | ⚠️ {delinquency['count']}건, {_won(delinquency['amount'])} (신규 여신 거절 대상) |")
    else:
        lines.append("| 미해결 연체 | 없음 |")

    if profile["loans"]:
        lines += ["", "**기존 대출**", "", "| 대출 ID | 상품 | 잔액 | 금리 | 남은 기간 | 연 상환액 |", "|------|------|------|------|------|------|"]
        for loan in profile["loans"]:
            lines.append(f"| {loan['loan_id']} | {loan['product_name']} | {loan['balance']:,}원 | {loan['interest_rate']}% "
                         f"| {loan['remaining_months']}개월 | {loan['annual_repayment']:,}원 |")
    lines += ["", "[출처: 고객 DB]"]
    return "\n".join(lines)
