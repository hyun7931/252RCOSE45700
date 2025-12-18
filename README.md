# 🏦 LIBO — Loan Intelligence Banking Officer
### 하이브리드 여신 심사 보조 AI 챗봇

**LIBO**는 금융권 여신 심사 업무를 보조하기 위해 설계된 **AI 기반 여신 심사 챗봇**입니다.  
정형 데이터(DB의 고객 정보)와 비정형 데이터(여신 규정, 약관, 상품설명서)를 결합하여  
**정확한 계산 + 근거 기반 판단**을 수행하는 하이브리드 여신 심사 시스템입니다.

---
## 🚀 배포 URL (Demo)
🔗 http://libo-frontend-251211.s3-website-us-east-1.amazonaws.com

*서비스 운영 기간: **12/11 ~ 12/21***

---
## 🎥 시연 영상 (Demo Video)
[![LIBO Demo Video](https://img.youtube.com/vi/HzkclE4IyNw/0.jpg)](https://youtu.be/HzkclE4IyNw)

---

## 📖 프로젝트 개요 (Overview)

기존 LLM 챗봇의  
✔ 숫자 계산 오류(Hallucination)  
✔ 최신 규정 미반영  
문제를 해결하기 위해,

**Deterministic Engine(심사 엔진)** + **RAG(Vector DB 기반 검색)** 를 결합한 구조로 설계되었습니다.

LIBO는 고객 소득·부채·신용 데이터를 기반으로 실제 **DSR·LTV·CSS** 계산을 수행하며,  
내규 기반 **전결 권한(지점/본부)** 여부까지 판정합니다.

---

## 💡 주요 기능 (Key Features)

### 🔹 1. Hybrid Architecture
- **Logic Engine (Deterministic Engine)**  
  - DSR / LTV 계산  
  - 상환액 산출  
  - CSS 등급 산출  
  - 전결 권한 판단  
  - 금리 스트레스 테스트
- **Knowledge Base (Vector DB: ChromaDB)**  
  - 규정집, 약관, 상품설명서를 임베딩  
  - RAG 기반 근거 제공

---

### 🔹 2. Stress Test 기능
- 금리가 +1% ~ +3% 상승했을 때  
  상환부담, DSR 변화, 부실 가능성 등을 시뮬레이션

---

## 💬 사용 예시 (Usage Scenarios)

### 1️⃣ 상품 및 규정 검색 (RAG)
> 벡터 DB에 저장된 규정집과 상품 설명서를 검색하여 답변합니다.
- “디디 직장인대출 최대한도 알려줘”
- “주담대 LTV 규제 얼마야?”
- “새희망홀씨 자격 알려줘”
- “중도상환수수료 면제 조건 있어?”

### 2️⃣ 여신 심사 시뮬레이션 (Logic Engine)
> 심사 엔진(Calculator Tool)을 호출하여 DSR과 CSS 등급을 실시간으로 계산합니다.
- [일반 심사]
  "연봉 6,000만 원, 신용점수 850점인 직장인이야. 기존 대출 상환액이 연 1,000만 원 있는데, 신용대출 1억 원 신청 가능해?"
- [스트레스 테스트]
  "그 상황에서 금리에서 2% 오르면 어떻게 변해?

---

## 📄 데이터 출처
* 학습, 연구 목적으로 데이터를 사용하였습니다.

### 📁 `backend/data/regulations`

#### (1) 여신심사 선진화 가이드라인.txt  
출처: 여신금융협회  
🔗 https://www.crefia.or.kr/portal/infocenter/regulation/selfRegulation.xx

#### (2) 은행여신거래기본약관.pdf  
출처: 국민은행  
🔗 https://obank.kbstar.com/quics?page=C021903&cc=b028364:b060739

#### (3) 은행 가계대출 상품설명서.pdf  
출처: 우리은행  
🔗 https://spot.wooribank.com/pot/Dream?withyou=CQFNT0023&cc=c007552:c027399

---

### 📁 `backend/data/products`

(아래 상품들은 **실제 금융상품을 기반으로 숫자 조정 및 규제 변경 후 학습용으로 사용**한 문서입니다.)

#### 1. 디디 새희망홀씨2.txt  
실제 출처: 신한 새희망홀씨Ⅱ  
🔗 https://m.shinhan.com/mw/fin/pg/PR0501S0600F01?mid=220011114000&pid=611115900&type=branch&hwno=

#### 2. 디디 자동차담보대출.txt  
실제 출처: 현대캐피탈 자동차담보대출  
🔗 https://www.hyundaicapital.com/seln/mtgvln/CPSLMV0101.hc

#### 3. 디디 주택담보대출.txt  
실제 출처: KB 주택담보대출  
🔗 https://obank.kbstar.com/quics?page=C103557&cc=b104363:b104516&isNew=N&prcode=LN20001160&QSL=F#loading

#### 4. 디디 직장인대출(인터넷뱅킹).txt  
실제 출처: 우리 주거래 직장인대출(인터넷뱅킹, 판매종료)  
🔗 https://spot.wooribank.com/pot/Dream?withyou=POLON0052&cc=c010528:c010531;c012425:c012399&PRD_CD=P020000054&PLM_PDCD=P020000054

---

### 📁 `backend/data/internal_rules`

#### 디디 내부 심사 규정.txt  
- LLM 기반 자체 생성 (여신심사가이드라인 참고하여 규정 모델링)

---

## 🛠️ 기술 스택 (Tech Stack)

| 영역 | 기술 |
|------|------|
| **Frontend** | React, Vite |
| **Backend** | FastAPI, Python |
| **AI / LLM** | LangChain, OpenAI GPT-4o-mini |
| **Vector DB** | ChromaDB |
| **Infra** | Docker, AWS EC2, AWS S3 |

---

## 🖥️ 향후 개발 예정 (TODO)
- [ ] Oracle DB 관련 수정 및 연동 (고객 실데이터 기반 심사)
- [ ] 규정, 전결 판정 수정
- [ ] RAG 성능 평가와 품질 개선
- [ ] LLM 캐싱
- [ ] 프론트엔드 UI 개선

---

## 😎 팀원 소개
* 이수현 (기획 및 개발)
