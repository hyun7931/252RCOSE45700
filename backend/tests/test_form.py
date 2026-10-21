# backend/tests/test_form.py
# 계산기 누락 응답 → 입력 폼 정보 변환 테스트

from app.rag.form import MISSING_MARKER, missing_message, build_form, form_prompt


def test_missing_message_round_trip():
    message = missing_message(["annual_income", "job_tenure"])
    assert message.startswith(MISSING_MARKER)
    assert "연소득, 재직 기간" in message

    form = build_form(message, {"loan_amount": 100000000, "product_type": "credit", "region": None})
    assert form == {
        "missing": ["annual_income", "job_tenure"],
        "prefilled": {"loan_amount": 100000000, "product_type": "credit"},  # None 값은 제외
    }


def test_build_form_ignores_other_results():
    assert build_form({"css": {"grade": 2}}, {}) is None
    assert build_form("[고객 없음] 고객 ID 'X'를 찾을 수 없습니다.", {}) is None


def test_form_prompt_lists_labels():
    assert "담보 주택 가액" in form_prompt(["collateral_value"])
