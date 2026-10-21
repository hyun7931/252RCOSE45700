# backend/tests/test_result_summary.py
# 심사 결과 표 렌더링과 LLM 해설 검증 테스트

from app.rag.result_summary import render_summary, check_commentary, is_calculation_result


def result(**overrides):
    r = {
        "css": {"total_score": 84.0, "grade": 3, "grade_band": "우량", "details": "..."},
        "dsr": {"current": 38.19, "stress": 47.96, "stress_rate_increase": "+2%p"},
        "required_authority": "본부 심사 필수 (2억 초과)",
        "user_role_check": "[권한 부족] 귀하(manager)는 승인할 수 없습니다. 상위 결재(본부 심사 필수 (2억 초과))를 요청하세요.",
        "risk_analysis": "금리 변동 리스크 안정적",
        "ltv": {"ratio": 50.0, "limit": 70.0, "region": "기타 일반지역", "max_loan": 560000000},
        "applied_conditions": {"금리": "4.0%", "대출 기간": "30년", "스트레스 금리 상승폭": "+2.0%p",
                               "기본값 적용 항목": ["스트레스 금리 상승폭 +2.0%p"]},
    }
    r.update(overrides)
    return r


def test_render_summary_contains_engine_numbers():
    text = render_summary(result())
    assert "| 판정 | 본부 심사 필수 (2억 초과) |" in text
    assert "| DSR | 38.19% |" in text
    assert "47.96%" in text
    assert "560,000,000원 (5억 6,000만 원)" in text
    assert "**기본값 적용**: 스트레스 금리 상승폭 +2.0%p" in text


def test_render_summary_credit_limit():
    text = render_summary(result(credit_limit=117141092))
    assert "117,141,092원 (1억 1,714만 원)" in text


def test_affirmative_blocked_without_authority():
    problems = check_commentary("신청하신 4억 원은 대출 가능합니다.", result())
    assert problems and "단정" in problems[0]


def test_affirmative_allowed_with_authority():
    approved = result(required_authority="영업점장 전결 (Branch Manager)",
                      user_role_check="[승인 가능] 귀하(manager)의 전결 권한 내입니다.")
    assert check_commentary("영업점장 전결로 승인 가능합니다.", approved) == []


def test_non_assertive_phrases_pass():
    text = "대출 가능 여부는 본부에서 최종 판단하며, 승인 가능성을 높이려면 자산 정보를 보완하세요."
    assert check_commentary(text, result()) == []


def test_unknown_percent_flagged():
    problems = check_commentary("DSR이 52%로 높습니다.", result())
    assert problems and "52%" in problems[0]


def test_known_percents_pass():
    text = "현재 DSR 38.19%는 본부 심사 기준 40% 아래이고, 금리가 2%p 오르면 47.96%로 50%에 가까워집니다. LTV 50%는 한도 70% 이내입니다."
    assert check_commentary(text, result()) == []


def test_is_calculation_result():
    assert is_calculation_result(result())
    assert not is_calculation_result("[필수 정보 누락] ...")
