# scripts/init_data.py
# 고객 DB 초기화: 테이블을 지우고 schema.sql로 다시 만든 뒤 데모 고객 + 랜덤 고객 데이터를 넣는다.
# 실행 (저장소 루트에서): backend/venv/Scripts/python scripts/init_data.py
# 접속 정보: backend/.env의 DB_HOST, DB_PORT, DB_SERVICE, DB_USER, DB_PASSWORD

import os
import random
from datetime import date, timedelta
from pathlib import Path

import oracledb
from dotenv import load_dotenv
from faker import Faker

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")

SEED = 2025
NUM_CUSTOMERS = 100
TABLES = ["DELINQUENCY_HISTORY", "LOAN_ACCOUNTS", "CUSTOMERS"]  # FK 때문에 자식 테이블부터 삭제

TODAY = date.today()


def months_ago(months, days=0):
    year, month = divmod(TODAY.year * 12 + TODAY.month - 1 - months, 12)
    return date(year, month + 1, min(TODAY.day, 28)) - timedelta(days=days)


def months_later(months):
    year, month = divmod(TODAY.year * 12 + TODAY.month - 1 + months, 12)
    return date(year, month + 1, min(TODAY.day, 28))


# README 사용 예시와 같은 상황의 데모 고객 (ID 고정)
DEMO_CUSTOMERS = [
    {   # 직장인 신용대출 1억 → 영업점장 전결
        "cust_id": "C2025_001", "name": "김디디", "birth": date(1988, 3, 14), "credit_score": 900,
        "income": 80000000, "company": "디디전자", "join": months_ago(42), "asset": 300000000,
        "payroll": "Y", "transfers": 3,
        "loans": [("L_DEMO_001", "직장인신용대출", 20000000, months_ago(12), months_later(48), 4.5)],
        "delinquencies": [],
    },
    {   # 직장인 신용대출 3천만 → 시스템 자동 승인
        "cust_id": "C2025_002", "name": "이디디", "birth": date(1985, 7, 2), "credit_score": 900,
        "income": 80000000, "company": "디디소프트", "join": months_ago(60), "asset": 300000000,
        "payroll": "Y", "transfers": 3, "loans": [], "delinquencies": [],
    },
    {   # 재직 1년 → 직장인대출 거절
        "cust_id": "C2025_003", "name": "박디디", "birth": date(1996, 11, 20), "credit_score": 850,
        "income": 60000000, "company": "디디물산", "join": months_ago(12), "asset": 0,
        "payroll": "N", "transfers": 0, "loans": [], "delinquencies": [],
    },
    {   # 주택담보대출 4억 (담보 8억, 일반지역) → 본부 심사, 금리 +3%p 시 DSR 50% 초과
        "cust_id": "C2025_004", "name": "최디디", "birth": date(1982, 5, 9), "credit_score": 900,
        "income": 60000000, "company": "디디건설", "join": months_ago(60), "asset": 500000000,
        "payroll": "Y", "transfers": 3, "loans": [], "delinquencies": [],
    },
]


def connect():
    dsn = f"{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '1521')}/{os.getenv('DB_SERVICE', 'XEPDB1')}"
    return oracledb.connect(user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], dsn=dsn)


def recreate_tables(cursor):
    for table in TABLES:
        try:
            cursor.execute(f"DROP TABLE {table} CASCADE CONSTRAINTS PURGE")
        except oracledb.DatabaseError:
            pass  # 테이블이 없으면 무시
    schema = (ROOT / "scripts" / "schema.sql").read_text(encoding="utf-8")
    for statement in schema.split(";"):
        lines = [ln for ln in statement.splitlines() if not ln.strip().startswith("--")]
        sql = "\n".join(lines).strip()
        if sql:
            cursor.execute(sql)


def insert_customer(cursor, c):
    cursor.execute(
        """
        INSERT INTO CUSTOMERS (CUST_ID, NAME, BIRTH_DATE, CREDIT_SCORE, ANNUAL_INCOME, COMPANY_NAME,
                               JOIN_DATE, ASSET_AMOUNT, HAS_PAYROLL, AUTO_TRANSFER_CNT)
        VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10)
        """,
        (c["cust_id"], c["name"], c["birth"], c["credit_score"], c["income"], c["company"],
         c["join"], c["asset"], c["payroll"], c["transfers"]),
    )
    for loan_id, product, balance, loan_date, maturity, rate in c["loans"]:
        cursor.execute(
            """
            INSERT INTO LOAN_ACCOUNTS (LOAN_ID, CUST_ID, PRODUCT_NAME, BALANCE_AMT, LOAN_DATE, MATURITY_DATE, INTEREST_RATE)
            VALUES (:1, :2, :3, :4, :5, :6, :7)
            """,
            (loan_id, c["cust_id"], product, balance, loan_date, maturity, rate),
        )
    for overdue_date, amount, resolved in c["delinquencies"]:
        cursor.execute(
            "INSERT INTO DELINQUENCY_HISTORY (CUST_ID, OVERDUE_DATE, OVERDUE_AMT, IS_RESOLVED) VALUES (:1, :2, :3, :4)",
            (c["cust_id"], overdue_date, amount, resolved),
        )


def random_customers(fake, rng):
    for i in range(len(DEMO_CUSTOMERS) + 1, NUM_CUSTOMERS + 1):
        cust_id = f"C2025_{i:03d}"
        credit_score = rng.randint(550, 1000)

        loans = []
        if rng.random() < 0.6:
            loan_date = TODAY - timedelta(days=rng.randint(365, 365 * 3))
            maturity = loan_date + timedelta(days=365 * rng.randint(4, 8))  # 만기가 미래가 되도록
            loans.append((f"L_{i:03d}_1", "직장인신용대출", rng.randint(1000, 10000) * 10000,
                          loan_date, maturity, round(rng.uniform(3.5, 7.0), 2)))

        delinquencies = []
        if credit_score < 700 and rng.random() < 0.3:
            delinquencies.append((TODAY - timedelta(days=rng.randint(1, 365)), rng.randint(10, 500) * 10000, "N"))

        yield {
            "cust_id": cust_id,
            "name": fake.name(),
            "birth": fake.date_of_birth(minimum_age=25, maximum_age=60),
            "credit_score": credit_score,
            "income": rng.randint(3000, 15000) * 10000,
            "company": fake.company(),
            "join": TODAY - timedelta(days=rng.randint(30, 365 * 10)),
            "asset": rng.randint(1000, 50000) * 10000,
            "payroll": "Y" if rng.random() < 0.5 else "N",
            "transfers": rng.randint(0, 5),
            "loans": loans,
            "delinquencies": delinquencies,
        }


def main():
    fake = Faker("ko_KR")
    Faker.seed(SEED)
    rng = random.Random(SEED)

    with connect() as conn:
        cursor = conn.cursor()
        recreate_tables(cursor)
        print("테이블 생성 완료")

        customers = DEMO_CUSTOMERS + list(random_customers(fake, rng))
        for c in customers:
            insert_customer(cursor, c)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM LOAN_ACCOUNTS")
        loans = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT CUST_ID) FROM DELINQUENCY_HISTORY WHERE IS_RESOLVED = 'N'")
        delinquent = cursor.fetchone()[0]
        print(f"고객 {len(customers)}명, 기존 대출 {loans}건, 미해결 연체 고객 {delinquent}명 생성 완료")


if __name__ == "__main__":
    main()
