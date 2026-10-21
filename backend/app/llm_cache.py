# backend/app/llm_cache.py
# LLM 응답 정확 일치 캐시 (SQLite). 의미 캐시는 쓰지 않음:
# "1억 가능해?"와 "2억 가능해?"처럼 문장은 비슷해도 결과가 다른 질문을 같은 것으로 볼 위험이 있음.
# 키는 질문 문장이 아니라 엔진 결과·검색 결과 같은 실제 데이터로 만든다.

import contextvars
import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PATH = BASE_DIR / "data" / "llm_cache.sqlite3"

_lock = threading.Lock()
PURGE_INTERVAL_SECONDS = 3600  # 오래된 캐시 정리는 프로세스당 최대 1시간에 한 번
_last_purge = 0.0
# 요청 하나 동안의 캐시 적중 기록 (예: {"router": True, "commentary": False})
_request_stats = contextvars.ContextVar("llm_cache_stats", default=None)


def enabled():
    return os.getenv("LLM_CACHE_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")


def cache_path():
    return Path(os.getenv("LLM_CACHE_PATH") or DEFAULT_PATH)


def ttl_days():
    """캐시 보관 기간(일). 0 이하면 만료 없음"""
    try:
        return float(os.getenv("LLM_CACHE_TTL_DAYS", "30"))
    except ValueError:
        return 30.0


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_key(kind, payload):
    """kind와 payload(JSON 직렬화 가능한 값)로 결정적인 캐시 키 생성"""
    body = json.dumps({"kind": kind, "payload": payload}, ensure_ascii=False, sort_keys=True, default=str)
    return f"{kind}:{text_hash(body)}"


def _connect():
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, "
                 "created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_cache_created_at ON llm_cache (created_at)")
    return conn


def _expiry_clause():
    """만료 조건 SQL (created_at은 UTC 'YYYY-MM-DD HH:MM:SS')"""
    days = ttl_days()
    if days <= 0:
        return "", ()
    return " AND created_at >= datetime('now', ?)", (f"-{days} days",)


def get(key):
    """만료되지 않은 값만 반환"""
    if not enabled():
        return None
    clause, params = _expiry_clause()
    with _lock, _connect() as conn:
        row = conn.execute("SELECT value FROM llm_cache WHERE key = ?" + clause, (key, *params)).fetchone()
    return json.loads(row[0]) if row else None


def put(key, value):
    """저장 (같은 키면 덮어쓰고 저장 시각도 새로 기록). 가끔 오래된 항목을 정리"""
    if not enabled():
        return
    with _lock, _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO llm_cache (key, value, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                     (key, json.dumps(value, ensure_ascii=False)))
    _maybe_purge()


def purge_expired():
    """보관 기간이 지난 항목 삭제. 삭제한 개수 반환"""
    days = ttl_days()
    if days <= 0:
        return 0
    with _lock, _connect() as conn:
        deleted = conn.execute("DELETE FROM llm_cache WHERE created_at < datetime('now', ?)",
                               (f"-{days} days",)).rowcount
    return deleted


def _maybe_purge():
    global _last_purge
    now = time.monotonic()
    if now - _last_purge >= PURGE_INTERVAL_SECONDS:
        _last_purge = now
        purge_expired()


def start_request():
    _request_stats.set({})


def record(kind, hit):
    stats = _request_stats.get()
    if stats is not None:
        stats[kind] = hit


def request_stats():
    return dict(_request_stats.get() or {})


def cached_call(kind, payload, compute):
    """캐시에 있으면 그 값, 없으면 compute()를 실행해 저장. compute가 None을 돌려주면 저장하지 않음"""
    key = make_key(kind, payload)
    value = get(key)
    if value is not None:
        record(kind, True)
        return value
    record(kind, False)
    value = compute()
    if value is not None:
        put(key, value)
    return value


if __name__ == "__main__":
    # 수동 정리: backend/에서 python -m app.llm_cache
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
    deleted = purge_expired()
    print(f"캐시 {total}건 중 {deleted}건 삭제 (보관 기간 {ttl_days():g}일, 경로 {cache_path()})")
