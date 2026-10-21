# backend/app/db/customer_repository.py
# Oracle 고객 DB 조회 (접속 정보: backend/.env의 DB_*)

import os
from dotenv import load_dotenv

from app.logic.customer_profile import build_profile

load_dotenv()


class CustomerDBError(Exception):
    pass


def get_connection():
    import oracledb  # thin 모드: Oracle 클라이언트 설치 불필요

    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    if not user or not password:
        raise CustomerDBError("backend/.env에 DB_USER, DB_PASSWORD가 설정되지 않았습니다.")
    dsn = f"{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '1521')}/{os.getenv('DB_SERVICE', 'XEPDB1')}"
    try:
        return oracledb.connect(user=user, password=password, dsn=dsn)
    except oracledb.Error as e:
        raise CustomerDBError(f"고객 DB 연결 실패 ({dsn}): {e}") from e


def _fetch_all(cursor, sql, params):
    cursor.execute(sql, params)
    columns = [c[0].lower() for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_customer_profile(customer_id):
    """고객 ID로 심사용 프로필 조회. 없으면 None"""
    customer_id = customer_id.strip().upper()
    with get_connection() as conn:
        cur = conn.cursor()
        customers = _fetch_all(cur, "SELECT * FROM CUSTOMERS WHERE CUST_ID = :1", [customer_id])
        if not customers:
            return None
        loans = _fetch_all(cur, "SELECT * FROM LOAN_ACCOUNTS WHERE CUST_ID = :1 ORDER BY LOAN_DATE", [customer_id])
        delinquencies = _fetch_all(cur, "SELECT * FROM DELINQUENCY_HISTORY WHERE CUST_ID = :1 ORDER BY OVERDUE_DATE", [customer_id])
    return build_profile(customers[0], loans, delinquencies)
