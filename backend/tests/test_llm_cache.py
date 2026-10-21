# backend/tests/test_llm_cache.py
# LLM 정확 일치 캐시 테스트 (임시 SQLite 파일 사용, LLM 불필요)

import pytest

from app import llm_cache


@pytest.fixture(autouse=True)
def temp_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_CACHE_PATH", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setenv("LLM_CACHE_ENABLED", "true")
    llm_cache.start_request()


RESULT = {"dsr": {"current": 35.15}, "applied_conditions": {"연소득": "80,000,000원", "재직 기간": "3년 6개월"}}


def test_key_is_deterministic_and_order_independent():
    a = llm_cache.make_key("commentary", {"result": RESULT, "model": "m"})
    b = llm_cache.make_key("commentary", {"model": "m", "result": dict(reversed(list(RESULT.items())))})
    assert a == b


@pytest.mark.parametrize("change", [
    {"dsr": {"current": 35.16}},                                                       # 숫자 하나
    {"applied_conditions": {"연소득": "80,000,000원", "재직 기간": "3년 7개월"}},           # DB 값·날짜로 바뀌는 재직 기간
])
def test_key_changes_with_any_result_value(change):
    base = llm_cache.make_key("commentary", {"result": RESULT})
    assert llm_cache.make_key("commentary", {"result": {**RESULT, **change}}) != base


def test_key_changes_with_model_and_kind():
    base = llm_cache.make_key("commentary", {"result": RESULT, "model": "gemini"})
    assert llm_cache.make_key("commentary", {"result": RESULT, "model": "openai"}) != base
    assert llm_cache.make_key("regulation", {"result": RESULT, "model": "gemini"}) != base


def test_cached_call_hits_second_time():
    calls = []
    compute = lambda: calls.append(1) or "해설"
    assert llm_cache.cached_call("commentary", {"x": 1}, compute) == "해설"
    assert llm_cache.request_stats() == {"commentary": False}
    assert llm_cache.cached_call("commentary", {"x": 1}, compute) == "해설"
    assert llm_cache.request_stats() == {"commentary": True}
    assert len(calls) == 1


def test_none_is_not_cached():
    assert llm_cache.cached_call("router", {"x": 1}, lambda: None) is None
    assert llm_cache.get(llm_cache.make_key("router", {"x": 1})) is None


def test_disabled(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_ENABLED", "false")
    calls = []
    for _ in range(2):
        llm_cache.cached_call("commentary", {"x": 1}, lambda: calls.append(1) or "해설")
    assert len(calls) == 2


def test_structured_value_round_trip():
    value = {"intent": "review", "loan_amount": 100000000, "fields": [1, 2]}
    key = llm_cache.make_key("router", {"message": "신용대출 1억 가능해?"})
    llm_cache.put(key, value)
    assert llm_cache.get(key) == value


# --- 오래된 캐시 만료·삭제 ---

def _age(key, days):
    """테스트용: 항목 저장 시각을 days일 전으로 바꿈"""
    with llm_cache._connect() as conn:
        conn.execute("UPDATE llm_cache SET created_at = datetime('now', ?) WHERE key = ?", (f"-{days} days", key))


def test_expired_entry_is_ignored_and_purged(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_TTL_DAYS", "30")
    old, new = llm_cache.make_key("router", {"x": "old"}), llm_cache.make_key("router", {"x": "new"})
    llm_cache.put(old, "예전 값")
    llm_cache.put(new, "새 값")
    _age(old, 31)
    assert llm_cache.get(old) is None          # 만료된 값은 쓰지 않음
    assert llm_cache.get(new) == "새 값"
    assert llm_cache.purge_expired() == 1      # 만료된 것만 삭제
    assert llm_cache.get(new) == "새 값"


def test_put_refreshes_timestamp(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_TTL_DAYS", "30")
    key = llm_cache.make_key("router", {"x": 1})
    llm_cache.put(key, "값")
    _age(key, 31)
    llm_cache.put(key, "다시 저장")
    assert llm_cache.get(key) == "다시 저장"


def test_ttl_zero_never_expires(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_TTL_DAYS", "0")
    key = llm_cache.make_key("router", {"x": 1})
    llm_cache.put(key, "값")
    _age(key, 3650)
    assert llm_cache.get(key) == "값"
    assert llm_cache.purge_expired() == 0
