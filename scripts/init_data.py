import oracledb
from faker import Faker
import random
from datetime import datetime, timedelta

# 1. Oracle DB 접속 정보 (XEPDB1)
dsn = oracledb.makedsn("localhost", 1521, service_name="xepdb1")

try:
    conn = oracledb.connect(user="bank_user", password="bank1234", dsn=dsn)
    cursor = conn.cursor()
    print("✅ Oracle DB 접속 성공")
except Exception as e:
    print(f"❌ Oracle DB 접속 실패: {e}")
    exit()

fake = Faker('ko_KR')

print("고객 데이터 생성 시작")

# 2. 고객 데이터 생성
cust_ids = []
for i in range(1, 101):
    cust_id = f"C2025_{i:03d}"
    cust_ids.append(cust_id)
    
    name = fake.name()
    birth = fake.date_of_birth(minimum_age=25, maximum_age=60)
    credit_score = random.randint(550, 1000)
    income = random.randint(3000, 15000) * 10000
    company = fake.company()
    join_date = fake.date_between(start_date='-10y', end_date='today')
    asset = random.randint(1000, 50000) * 10000 

    sql = """
        INSERT INTO CUSTOMERS (CUST_ID, NAME, BIRTH_DATE, CREDIT_SCORE, ANNUAL_INCOME, COMPANY_NAME, JOIN_DATE, ASSET_AMOUNT)
        VALUES (:1, :2, :3, :4, :5, :6, :7, :8)
    """
    cursor.execute(sql, (cust_id, name, birth, credit_score, income, company, join_date, asset))

# 3. 기대출 데이터 생성
for cust_id in cust_ids:
    if random.random() < 0.6: 
        loan_id = f"L_{random.randint(10000, 99999)}"
        balance = random.randint(1000, 10000) * 10000
        rate = round(random.uniform(3.5, 7.0), 2)
        loan_date = fake.date_between(start_date='-3y', end_date='-1y')
        # 만기일은 대출일로부터 1~5년 뒤로 랜덤 설정
        maturity_date = loan_date + timedelta(days=365 * random.randint(1, 5))
        
        sql = """
            INSERT INTO LOAN_ACCOUNTS (LOAN_ID, CUST_ID, PRODUCT_NAME, BALANCE_AMT, LOAN_DATE, MATURITY_DATE, INTEREST_RATE)
            VALUES (:1, :2, :3, :4, :5, :6, :7)
        """
        cursor.execute(sql, (loan_id, cust_id, "직장인신용대출", balance, loan_date, maturity_date, rate))

# 4. 연체 이력 생성
for cust_id in cust_ids:
    cursor.execute("SELECT CREDIT_SCORE FROM CUSTOMERS WHERE CUST_ID = :1", (cust_id,))
    score = cursor.fetchone()[0]
    
    if score < 700 and random.random() < 0.3:
        overdue_amt = random.randint(10, 500) * 10000
        overdue_date = fake.date_between(start_date='-1y', end_date='today')
        
        sql = """
            INSERT INTO DELINQUENCY_HISTORY (CUST_ID, OVERDUE_DATE, OVERDUE_AMT, IS_RESOLVED)
            VALUES (:1, :2, :3, 'N')
        """
        cursor.execute(sql, (cust_id, overdue_date, overdue_amt))

conn.commit()
print("고객 데이터 생성 완료")
cursor.close()
conn.close()