-- 디디은행 고객 DB 스키마 (Oracle)
-- scripts/init_data.py가 기존 테이블을 지우고 이 파일로 다시 만든다.

CREATE TABLE CUSTOMERS (
    CUST_ID            VARCHAR2(20)   PRIMARY KEY,
    NAME               VARCHAR2(50)   NOT NULL,
    BIRTH_DATE         DATE,
    CREDIT_SCORE       NUMBER(4)      NOT NULL,
    ANNUAL_INCOME      NUMBER(15)     NOT NULL,
    COMPANY_NAME       VARCHAR2(100),
    JOIN_DATE          DATE,                                   -- 현 직장 입사일 (재직 기간 산출)
    ASSET_AMOUNT       NUMBER(15)     DEFAULT 0 NOT NULL,      -- 보유 자산 (부동산 + 예금)
    HAS_PAYROLL        CHAR(1)        DEFAULT 'N' NOT NULL CHECK (HAS_PAYROLL IN ('Y', 'N')),  -- 당행 급여이체
    AUTO_TRANSFER_CNT  NUMBER(3)      DEFAULT 0 NOT NULL       -- 당행 자동이체 건수
);

CREATE TABLE LOAN_ACCOUNTS (
    LOAN_ID        VARCHAR2(20)   PRIMARY KEY,
    CUST_ID        VARCHAR2(20)   NOT NULL REFERENCES CUSTOMERS (CUST_ID),
    PRODUCT_NAME   VARCHAR2(100),
    BALANCE_AMT    NUMBER(15)     NOT NULL,                    -- 대출 잔액
    LOAN_DATE      DATE           NOT NULL,
    MATURITY_DATE  DATE           NOT NULL,
    INTEREST_RATE  NUMBER(5, 2)   NOT NULL                     -- 연 금리 (%)
);

CREATE TABLE DELINQUENCY_HISTORY (
    DELINQ_ID     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    CUST_ID       VARCHAR2(20)   NOT NULL REFERENCES CUSTOMERS (CUST_ID),
    OVERDUE_DATE  DATE           NOT NULL,
    OVERDUE_AMT   NUMBER(15)     NOT NULL,
    IS_RESOLVED   CHAR(1)        DEFAULT 'N' NOT NULL CHECK (IS_RESOLVED IN ('Y', 'N'))
);
