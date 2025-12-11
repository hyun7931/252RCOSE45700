# backend/app/logic/loan_engine.py

class LoanReviewEngine:
    def __init__(self):
        self.DSR_LIMIT_NORMAL = 0.40
        self.DSR_LIMIT_CONDITIONAL = 0.50
        
        self.LTV_LIMITS = {
            "speculative": 0.50,
            "adjusted": 0.60,
            "normal": 0.70
        }

    def calculate_css_score(self, nice_score, income, has_payroll, auto_transfers, job_years):
        """
        [규정] 제2장: 내부 등급 평가 (CSS Scoring) 구현
        """
        #1. 신용도 40
        #2. 상환능력 30
        #3. 거래기여도 20
        #4. 직업안정성 10
        score_credit = min((nice_score / 1000) * 40, 40)
        score_income = min((income / 100000000) * 30, 30)
        score_trans = 0
        if has_payroll: score_trans += 10
        if auto_transfers >= 3: score_trans += 10
        score_job = 0
        if job_years >= 3: score_job = 10
        elif job_years >= 1: score_job = 5
        
        total_score = round(score_credit + score_income + score_trans + score_job, 1)
        
        #등급 판정
        if total_score >= 90: grade = 1
        elif total_score >= 80: grade = 2
        elif total_score >= 70: grade = 3
        elif total_score >= 60: grade = 4
        else: grade = 5
        
        return {
            "total_score": total_score,
            "grade": grade,
            "details": f"신용({score_credit:.1f}) + 소득({score_income:.1f}) + 거래({score_trans}) + 안정성({score_job})"
        }

    def calculate_dsr(self, annual_income, current_annual_debt, new_loan_amt, interest_rate, duration_years):
        #MVP : 원리금 균등 상환
        if annual_income == 0: return 999.0
        
        monthly_rate = interest_rate / 12
        num_payments = duration_years * 12
        
        if interest_rate == 0:
            monthly_payment = new_loan_amt / num_payments
        else:
            monthly_payment = new_loan_amt * (monthly_rate * (1 + monthly_rate) ** num_payments) / ((1 + monthly_rate) ** num_payments - 1)
            
        new_annual_payment = monthly_payment * 12
        total_annual_payment = current_annual_debt + new_annual_payment
        
        dsr = total_annual_payment / annual_income
        return round(dsr, 4)

    def determine_approval_authority(self, loan_amount, grade, dsr, product_type="credit"):
        """
        [규정] 제3장: 전결 권한 판정 (권한 레벨 반환)
        Level 0: 자동승인 / Level 1: 지점장 / Level 2: 본부 / Level 99: 거절
        """
        #자동 거절
        if grade >= 5: 
             return {"level": 99, "type": "❌ 거절 (Reject: 내부등급 미달)"}
        if dsr > 0.70:
             return {"level": 99, "type": "❌ 거절 (Reject: DSR 70% 초과)"}

        #자동 승인
        if loan_amount <= 50000000 and grade <= 3 and dsr <= 0.30:
            return {"level": 0, "type": "✅ 시스템 자동 승인 (System Approval)"}
        
        #심사 필요
        reasons = []
        if loan_amount > 200000000: reasons.append("2억 초과")
        if product_type == "mortgage" and dsr > 0.40: reasons.append("주담대 DSR 40% 초과")
        if product_type == "policy" and dsr > 0.50: reasons.append("새희망홀씨 고DSR 특례")
        
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
        
        req_amt = loan_request.get('amount', 0)
        req_rate = loan_request.get('rate', 0.05)
        req_term = loan_request.get('term', 5)
        prod_type = loan_request.get('product_type', 'credit')
        #CSS 계산
        css_result = self.calculate_css_score(
            nice, income, 
            user_data.get('has_payroll', False),
            user_data.get('auto_transfers', 0),
            user_data.get('job_years', 0)
        )
        
        #DSR 계산
        dsr = self.calculate_dsr(income, cur_debt_pay, req_amt, req_rate, req_term)
        stress_dsr = self.calculate_dsr(income, cur_debt_pay, req_amt, req_rate + 0.02, req_term)
        
        #판정 필요 레벨과 사용자
        required_auth = self.determine_approval_authority(req_amt, css_result['grade'], dsr, prod_type)
        final_judgment = self.check_user_authority(required_auth, user_role)
        
        return {
            "css": css_result,
            "dsr": {"current": dsr * 100, "stress": stress_dsr * 100},
            "required_authority": required_auth['type'],
            "user_role_check": final_judgment,
            "risk_analysis": "금리 상승 시 DSR 규제(40%) 초과 위험" if stress_dsr > 0.4 else "금리 변동 리스크 안정적"
        }

# 테스트용 실행 코드
if __name__ == "__main__":
    engine = LoanReviewEngine()
    
    test_user = {
        "annual_income": 60000000,
        "credit_score": 850,
        "current_annual_repayment": 10000000,
        "has_payroll": True, "auto_transfers": 3, "job_years": 4
    }
    
    # 테스트 케이스: 3억 대출 (본부 심사 대상)
    test_req = {
        "amount": 300000000, 
        "rate": 0.05, "term": 10, "product_type": "credit"
    }
    
    # 1. 지점장(Manager) 권한으로 시도 -> 권한 부족 떠야 함
    print("--- 지점장(Manager) 시뮬레이션 ---")
    result_manager = engine.run_simulation(test_user, test_req, user_role="manager")
    print(f"결과: {result_manager['user_role_check']}")

    # 2. 본부(HQ) 권한으로 시도 -> 승인 가능 떠야 함
    print("\n--- 본부(HQ) 시뮬레이션 ---")
    result_hq = engine.run_simulation(test_user, test_req, user_role="hq")
    print(f"결과: {result_hq['user_role_check']}")