# backend/app/logic/loan_engine.py
# 규정 근거: data/regulations/internal_rules/디디 내부심사규정.txt

class LoanReviewEngine:
    def __init__(self):
        self.DSR_LIMIT_NORMAL = 0.40          # 본부 심사 기준, 직장인대출 DSR 한도 내 금액 기준
        self.DSR_LIMIT_REJECT = 0.50          # 초과 시 거절 (새희망홀씨 제외)
        self.DSR_LIMIT_POLICY_HQ = 0.70       # 새희망홀씨 본부 심사 기준
        self.STRESS_DSR_LIMIT = 0.50          # 제5장 금리 인상 시나리오 기준

        # 제2장 3항 점수별 등급 기준 (1~14등급 하한 점수, 그 미만은 15등급)
        self.GRADE_CUTOFFS = [90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25]

        # 제3장 1항 직장인대출
        self.CREDIT_MIN_JOB_MONTHS = 24
        self.CREDIT_REJECT_GRADE = 9
        self.CREDIT_MAX_LIMIT = 150000000

        # 제4장 4항 거절 등급 (새희망홀씨 10등급 이내 승인 특례도 이 기준으로 충족)
        self.REJECT_GRADE = 11

        # TODO(#9): 주택담보대출 LTV 판정에 사용
        self.LTV_LIMITS = {
            "speculative": 0.50,
            "adjusted": 0.60,
            "normal": 0.70
        }

    def calculate_css_score(self, nice_score, income, has_payroll, auto_transfers, asset_amount):
        """
        [규정] 제2장: 내부 등급 평가 (CSS Scoring) 구현
        """
        #1. 신용도 40
        #2. 상환능력 30
        #3. 거래기여도 20
        #4. 자산안정성 10
        score_credit = min((nice_score / 1000) * 40, 40)
        score_income = min((income / 100000000) * 30, 30)
        score_trans = 0
        if has_payroll: score_trans += 10
        if auto_transfers >= 3: score_trans += 10
        score_asset = min((asset_amount / 500000000) * 10, 10)

        total_score = round(score_credit + score_income + score_trans + score_asset, 1)

        grade = self.score_to_grade(total_score)

        return {
            "total_score": total_score,
            "grade": grade,
            "grade_band": self.grade_band(grade),
            "details": f"신용({score_credit:.1f}) + 소득({score_income:.1f}) + 거래({score_trans}) + 자산({score_asset:.1f})"
        }

    def score_to_grade(self, total_score):
        """[규정] 제2장 3항: 점수별 등급 기준"""
        for i, cutoff in enumerate(self.GRADE_CUTOFFS):
            if total_score >= cutoff:
                return i + 1
        return len(self.GRADE_CUTOFFS) + 1

    def grade_band(self, grade):
        if grade <= 4: return "우량"
        if grade <= 7: return "일반"
        if grade <= 10: return "주의"
        return "위험"

    def annual_payment(self, loan_amt, interest_rate, duration_years):
        #MVP : 원리금 균등 상환
        num_payments = duration_years * 12
        if interest_rate == 0:
            monthly_payment = loan_amt / num_payments
        else:
            monthly_rate = interest_rate / 12
            monthly_payment = loan_amt * (monthly_rate * (1 + monthly_rate) ** num_payments) / ((1 + monthly_rate) ** num_payments - 1)
        return monthly_payment * 12

    def calculate_dsr(self, annual_income, current_annual_debt, new_loan_amt, interest_rate, duration_years):
        if annual_income == 0: return 999.0

        total_annual_payment = current_annual_debt + self.annual_payment(new_loan_amt, interest_rate, duration_years)
        dsr = total_annual_payment / annual_income
        return round(dsr, 4)

    def max_loan_within_dsr(self, annual_income, current_annual_debt, interest_rate, duration_years, dsr_limit):
        """DSR이 dsr_limit를 넘지 않는 최대 신규 대출 금액"""
        capacity = annual_income * dsr_limit - current_annual_debt
        if capacity <= 0:
            return 0
        # 연 상환액은 원금에 비례하므로 1원당 연 상환액으로 역산
        return int(capacity / self.annual_payment(1, interest_rate, duration_years))

    def calculate_credit_limit(self, annual_income, current_annual_debt, interest_rate, duration_years, grade):
        """
        [규정] 제3장 1항 다: 직장인대출 한도 산출
        """
        income_multiple = 1.0 if grade >= 5 else 1.5
        dsr_amount = self.max_loan_within_dsr(annual_income, current_annual_debt, interest_rate, duration_years, self.DSR_LIMIT_NORMAL)
        return int(min(annual_income * income_multiple, self.CREDIT_MAX_LIMIT, dsr_amount))

    def determine_approval_authority(self, loan_amount, grade, dsr, product_type="credit", job_months=0, credit_limit=None):
        """
        [규정] 제3장 컷오프, 제4장: 전결 권한 판정 (권한 레벨 반환)
        Level 0: 자동승인 / Level 1: 지점장 / Level 2: 본부 / Level 99: 거절
        """
        #거절
        reject = []
        if grade >= self.REJECT_GRADE:
            reject.append(f"내부등급 {grade}등급 (위험 구간)")
        if product_type != "policy" and dsr > self.DSR_LIMIT_REJECT:
            reject.append(f"DSR {self.DSR_LIMIT_REJECT:.0%} 초과")
        if product_type == "credit":
            if job_months < self.CREDIT_MIN_JOB_MONTHS:
                reject.append(f"재직기간 {self.CREDIT_MIN_JOB_MONTHS}개월 미만")
            if grade >= self.CREDIT_REJECT_GRADE:
                reject.append(f"직장인대출 {self.CREDIT_REJECT_GRADE}등급 이하")
            if credit_limit is not None and loan_amount > credit_limit:
                reject.append(f"한도({credit_limit:,}원) 초과")
        if reject:
            return {"level": 99, "type": f"❌ 거절 (Reject: {', '.join(dict.fromkeys(reject))})"}

        #자동 승인
        if loan_amount <= 50000000 and grade <= 3 and dsr <= 0.30:
            return {"level": 0, "type": "✅ 시스템 자동 승인 (System Approval)"}

        #심사 필요
        reasons = []
        if loan_amount > 200000000: reasons.append("2억 초과")
        if product_type == "policy":
            if dsr > self.DSR_LIMIT_POLICY_HQ: reasons.append(f"새희망홀씨 DSR {self.DSR_LIMIT_POLICY_HQ:.0%} 초과")
        elif dsr > self.DSR_LIMIT_NORMAL:
            reasons.append(f"DSR {self.DSR_LIMIT_NORMAL:.0%} 초과 예외 승인")
        if 7 <= grade <= 10: reasons.append(f"내부등급 {grade}등급")

        if reasons:
            return {"level": 2, "type": f"본부 심사 필수 ({', '.join(reasons)})"}

        #전결
        return {"level": 1, "type": "영업점장 전결 (Branch Manager)"}

    def check_user_authority(self, required_auth, user_role):
        role_map = {"staff": 0, "manager": 1, "hq": 2}
        user_level = role_map.get(user_role, 0)

        if required_auth['level'] == 99:
            return "[System Reject] 규정상 취급 불가 대상입니다."

        if user_level >= required_auth['level']:
            return f"[승인 가능] 귀하({user_role})의 전결 권한 내입니다."
        else:
            return f"[권한 부족] 귀하({user_role})는 승인할 수 없습니다. 상위 결재({required_auth['type']})를 요청하세요."

    def run_simulation(self, user_data, loan_request, user_role="manager"):
        income = user_data.get('annual_income', 0)
        nice = user_data.get('credit_score', 0)
        cur_debt_pay = user_data.get('current_annual_repayment', 0)
        job_months = user_data.get('job_months', 0)

        req_amt = loan_request.get('amount', 0)
        req_rate = loan_request.get('rate', 0.05)
        req_term = loan_request.get('term', 5)
        stress_add = loan_request.get('stress_rate_increase', 0.02)
        prod_type = loan_request.get('product_type', 'credit')
        #CSS 계산
        css_result = self.calculate_css_score(
            nice, income,
            user_data.get('has_payroll', False),
            user_data.get('auto_transfers', 0),
            user_data.get('asset_amount', 0)
        )

        #DSR 계산
        dsr = self.calculate_dsr(income, cur_debt_pay, req_amt, req_rate, req_term)
        stress_dsr = self.calculate_dsr(income, cur_debt_pay, req_amt, req_rate + stress_add, req_term)

        #직장인대출 한도
        credit_limit = None
        if prod_type == "credit":
            credit_limit = self.calculate_credit_limit(income, cur_debt_pay, req_rate, req_term, css_result['grade'])

        #판정 필요 레벨과 사용자
        required_auth = self.determine_approval_authority(req_amt, css_result['grade'], dsr, prod_type, job_months, credit_limit)
        final_judgment = self.check_user_authority(required_auth, user_role)

        result = {
            "css": css_result,
            "dsr": {"current": round(dsr * 100, 2), "stress": round(stress_dsr * 100, 2), "stress_rate_increase": f"+{stress_add * 100:g}%p"},
            "required_authority": required_auth['type'],
            "user_role_check": final_judgment,
            "risk_analysis": f"금리 상승 시 DSR {self.STRESS_DSR_LIMIT:.0%} 초과 위험 (내부심사규정 제5장)" if stress_dsr > self.STRESS_DSR_LIMIT else "금리 변동 리스크 안정적"
        }
        if credit_limit is not None:
            result["credit_limit"] = credit_limit
        return result

# 테스트용 실행 코드
if __name__ == "__main__":
    engine = LoanReviewEngine()

    test_user = {
        "annual_income": 100000000,
        "credit_score": 900,
        "current_annual_repayment": 5000000,
        "has_payroll": True, "auto_transfers": 3, "job_months": 48,
        "asset_amount": 300000000
    }

    # 테스트 케이스: 3억 대출 (본부 심사 대상)
    test_req = {
        "amount": 300000000,
        "rate": 0.05, "term": 30, "product_type": "mortgage"
    }

    # 1. 지점장(Manager) 권한으로 시도 -> 권한 부족 떠야 함
    print("--- 지점장(Manager) 시뮬레이션 ---")
    result_manager = engine.run_simulation(test_user, test_req, user_role="manager")
    print(f"결과: {result_manager['user_role_check']}")

    # 2. 본부(HQ) 권한으로 시도 -> 승인 가능 떠야 함
    print("\n--- 본부(HQ) 시뮬레이션 ---")
    result_hq = engine.run_simulation(test_user, test_req, user_role="hq")
    print(f"결과: {result_hq['user_role_check']}")
