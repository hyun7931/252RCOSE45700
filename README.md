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

LIBO는 고객 소득·부채·신용·자산 데이터를 기반으로 실제 **CSS 등급·DSR·대출 한도** 계산을 수행하며,  
내규 기반 **전결 권한(자동 승인/영업점장/본부/거절)** 여부까지 판정합니다.

📄 기능 상세: [docs/features.md](docs/features.md)

---

## 💡 주요 기능 (Key Features)

### 🔹 1. Hybrid Architecture
- **Logic Engine (Deterministic Engine)**: 디디 내부심사규정을 코드로 옮긴 심사 엔진
  - CSS 내부 등급 산출 (1~15등급: 신용도·상환능력·거래기여도·자산안정성)
  - DSR 계산 (원리금 균등 상환)
  - 직장인대출 한도 산출 및 컷오프 (재직 24개월, 9등급)
  - 전결 권한 판정 (자동 승인 / 영업점장 / 본부 / 거절) 및 사용자 직급별 승인 가능 여부
  - 금리 스트레스 테스트
- **Knowledge Base (Vector DB: ChromaDB)**
  - 규정집, 약관, 상품설명서를 임베딩
  - RAG 기반 근거 제공 (답변마다 출처 표시)

### 🔹 2. Stress Test 기능
- 금리가 오른 상황(기본 +2%p, "3% 오르면?"처럼 원하는 폭 지정 가능)의 DSR을 다시 계산
- 내부심사규정 기준(DSR 50%)을 넘으면 금리 상승 리스크로 경고

### 🔹 3. LLM Provider 선택
- `.env`의 `LLM_PROVIDER`(채팅)와 `EMBEDDING_PROVIDER`(임베딩)로 Google Gemini / OpenAI 선택

### 🔹 4. 채팅 UI
- 추천 질문 카드, 마크다운 답변 렌더링(표·목록), 대화 맥락 유지

---

## 💬 사용 예시 (Usage Scenarios)

### 1️⃣ 상품 및 규정 검색 (RAG)
> 벡터 DB에 저장된 규정집과 상품 설명서를 검색하여 출처와 함께 답변합니다.
- "디디 직장인대출 최대한도 알려줘"
- "투기과열지구 주담대 LTV 얼마야?"
- "새희망홀씨 대출 대상이 누구야?"
- "자동차담보대출 중도상환수수료 얼마야?"
- "내부등급 몇 등급부터 본부 심사야?"

### 2️⃣ 여신 심사 시뮬레이션 (Logic Engine)
> 심사 엔진(`loan_calculator`)을 호출하여 등급·DSR·한도·전결 권한을 계산합니다.  
> 금리·기간·급여이체·자동이체·보유 자산을 말하지 않으면 기본값으로 계산하고 답변에 안내합니다.

- **[승인 · 영업점장 전결]**  
  "연봉 8천, 신용 900점, 재직 3년 6개월 직장인이야. 기존 상환 연 500만 원, 급여이체·자동이체 3건 있고 자산 3억. 금리 5%, 5년으로 직장인 신용대출 1억 가능해?"  
  → 2등급, DSR 34.56%, 한도 약 1.19억 원, 영업점장 전결
- **[자동 승인]**  
  "연봉 8천, 신용 900점, 재직 5년, 기존 대출 없음, 급여이체·자동이체 3건, 자산 3억. 직장인 신용대출 3천만 원 가능해?"  
  → 2등급, DSR 8.49%, 시스템 자동 승인
- **[거절]**  
  "연봉 6천, 신용 850점, 재직 1년 직장인이야. 기존 대출 없고 직장인 신용대출 3천만 원 가능해?"  
  → 재직 24개월 미만으로 거절
- **[본부 심사 + 스트레스 테스트]**  
  "연봉 6천, 신용 900점, 재직 5년, 급여이체·자동이체 3건, 자산 5억. 주택담보대출 4억 원, 금리 4%, 30년이면?"  
  → 3등급, DSR 38.19%, 2억 초과로 본부 심사 (지점장은 권한 부족)  
  "그 상황에서 금리가 3% 오르면 어떻게 돼?"  
  → 스트레스 DSR 53.22%, 금리 상승 시 DSR 50% 초과 위험

---

## ⚙️ 실행 방법 (Getting Started)

### Backend
Python 3.11 권장 (Windows에서는 `chroma-hnswlib`에 3.12용 빌드 파일이 없음)

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # LLM_PROVIDER, API 키 입력
python -m app.rag.vector_store    # 벡터 DB 생성 (규정 문서·임베딩 provider 변경 시 다시 실행)
uvicorn app.main:app --reload --port 8000
python -m pytest                  # 심사 엔진 테스트
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## 📄 데이터 출처
* 학습, 연구 목적으로 데이터를 사용하였습니다.

### 📁 `backend/data/regulations/guidelines`

#### (1) 여신심사 선진화를 위한 가이드라인.txt  
출처: 여신금융협회  
🔗 https://www.crefia.or.kr/portal/infocenter/regulation/selfRegulation.xx

#### (2) 국민은행_은행여신거래기본약관.pdf  
출처: 국민은행  
🔗 https://obank.kbstar.com/quics?page=C021903&cc=b028364:b060739

#### (3) 우리은행가계대출상품설명서.pdf  
출처: 우리은행  
🔗 https://spot.wooribank.com/pot/Dream?withyou=CQFNT0023&cc=c007552:c027399

---

### 📁 `backend/data/regulations/products`

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

#### 4. 디디 직장인대출 (인터넷뱅킹).txt  
실제 출처: 우리 주거래 직장인대출(인터넷뱅킹, 판매종료)  
🔗 https://spot.wooribank.com/pot/Dream?withyou=POLON0052&cc=c010528:c010531;c012425:c012399&PRD_CD=P020000054&PLM_PDCD=P020000054

---

### 📁 `backend/data/regulations/internal_rules`

#### 디디 내부심사규정.txt  
- LLM 기반 자체 생성 (여신심사가이드라인 참고하여 규정 모델링)
- 심사 엔진 구현에 맞춰 등급 변환표·전결 조건 등 빈 곳 보완

---

## 🛠️ 기술 스택 (Tech Stack)

| 영역 | 기술 |
|------|------|
| **Frontend** | React 17, Vite, react-markdown |
| **Backend** | FastAPI, Python 3.11, pytest |
| **AI / LLM** | LangChain, Google Gemini / OpenAI (`LLM_PROVIDER`로 선택) |
| **Vector DB** | ChromaDB |
| **Infra** | Docker, AWS EC2, AWS S3 |

---
## 🤖 아키텍처
<img width="1494" height="571" alt="image" src="https://github.com/user-attachments/assets/5080c287-2c5a-4cf1-a795-e250a15182da" />

* **지식 구축 파이프라인**
  
  문서 (PDF, TXT) 
  → Chunking 
      - RecursiveCharacterTextSplitter
      - 1000 / 200 overlap
  → Embedding
      - Gemini / OpenAI Embedding
  → chromaDB 저장

* **검색 및 답변 파이프라인**
  
  사용자 질문
  → Embedding (Gemini / OpenAI)
  → 유사도 검색
  → prompt 통합
  → LLM (Gemini / OpenAI)
  → 답변 생성

---

## 🖥️ 향후 개발 예정 (TODO)
- [x] LLM provider 선택 (Gemini / OpenAI) (#1)
- [x] 심사 계산기 입력 항목 확장 (#2)
- [x] 내부심사규정 기준 등급·전결 판정 (#3)
- [x] 챗봇 응답 마크다운 렌더링 (#4)
- [ ] Oracle 고객 DB 연동 (#5)
- [ ] 심사 입력값 누락 시 입력 폼 (#7)
- [ ] 담보대출(LTV)·새희망홀씨 세부 심사 규칙 (#9)
- [ ] RAG 성능 평가와 품질 개선
- [ ] LLM 캐싱


---

## 😎 팀원 소개
* 이수현 (기획 및 개발)
