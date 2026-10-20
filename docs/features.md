# LIBO 기능 정리

LIBO는 디디은행 여신 심사역을 돕는 챗봇입니다. 사용자가 자연어로 질문하면 LangChain 에이전트(Gemini 또는 OpenAI 모델)가 질문 의도를 파악해 아래 두 도구 중 필요한 것을 호출하고, 결과를 근거(출처)와 함께 답변합니다.

| 도구 | 역할 | 구현 |
|------|------|------|
| `loan_calculator` | DSR·CSS 등급·전결 권한·스트레스 테스트 계산 | `backend/app/logic/loan_engine.py` |
| `regulatory_search` | 규정·약관·상품설명서 검색 (RAG) | `backend/app/rag/vector_store.py` |

---

## 1. 대화형 심사 보조 (Agent)

- 위치: `backend/app/rag/chatbot.py`
- 역할 설정: "디디은행 베테랑 여신 심사역 보조 AI, 디디 봇"
- 행동 규칙 (시스템 프롬프트)
  1. **필수 정보 확인** — 심사 계산 전에 연소득, 신용점수, 기존 대출 상환액, 대출 신청 금액, 재직 기간, 상품 종류를 확인하고, 빠진 정보는 먼저 되묻습니다.
  2. **수치 계산** — 정보가 모이면 `loan_calculator`로 DSR과 등급을 계산합니다.
  3. **규정 검색** — 금리·한도 등 상품 조건은 `regulatory_search`로 확인합니다.
  4. **출처 명시** — 모든 답변 끝에 `[출처: 파일명 / 규정 조항 / 내부 심사 엔진 결과]`를 붙입니다.
- 대화 기록: 서버에 저장하지 않습니다. 프론트엔드가 매 요청마다 전체 대화(`history`)를 함께 보내므로 "그 상황에서 금리가 2% 오르면?" 같은 후속 질문이 가능합니다.
- 오류 시 "내부 시스템 오류로 답변을 생성할 수 없습니다."를 반환합니다.

## 2. 여신 심사 엔진 (`loan_calculator`)

LLM이 숫자를 직접 계산하지 않고, 규칙 기반 엔진(`LoanReviewEngine`)이 계산합니다. 규칙은 `data/regulations/internal_rules/디디 내부심사규정.txt`를 코드로 옮긴 것입니다.

### 입력값

| 항목 | 설명 | 기본값 |
|------|------|--------|
| `annual_income` | 연소득(원) | 필수 |
| `credit_score` | NICE 신용점수 | 필수 |
| `loan_amount` | 신규 대출 신청 금액(원) | 필수 |
| `current_annual_repayment` | 기존 대출 연간 원리금 상환액(원) | 0 |
| `product_type` | `credit`(직장인신용) / `mortgage`(주택담보) / `auto`(자동차) / `policy`(새희망홀씨) | `credit` |
| `job_years` | 재직 기간(년) | 0 |
| `user_role` | 사용자 직급: `staff`(행원) / `manager`(지점장) / `hq`(본부심사역) | `manager` |

도구 내부에 고정된 값: 금리 5%, 대출 기간 5년, 급여이체 있음, 자동이체 3건.

### 2-1. 내부 신용등급 (CSS)

| 항목 | 배점 | 계산 |
|------|------|------|
| 신용도 | 40 | (NICE 점수 / 1000) × 40 |
| 상환능력 | 30 | (연소득 / 1억) × 30, 최대 30 |
| 거래기여도 | 20 | 급여이체 +10, 자동이체 3건 이상 +10 |
| 직업안정성 | 10 | 재직 3년 이상 10, 1년 이상 5 |

총점 → 등급: 90↑ 1등급 / 80↑ 2등급 / 70↑ 3등급 / 60↑ 4등급 / 그 외 5등급

### 2-2. DSR

- 신규 대출은 **원리금 균등 상환**으로 연 상환액을 계산합니다.
- DSR = (기존 연 상환액 + 신규 연 상환액) / 연소득

### 2-3. 금리 스트레스 테스트

- 금리를 **+2%p** 올려 DSR을 다시 계산합니다.
- 스트레스 DSR이 40%를 넘으면 "금리 상승 시 DSR 규제(40%) 초과 위험", 아니면 "금리 변동 리스크 안정적"으로 표시합니다.

### 2-4. 전결 권한 판정

| 레벨 | 결과 | 조건 |
|------|------|------|
| 99 | ❌ 거절 | 5등급, 또는 DSR 70% 초과 |
| 0 | ✅ 시스템 자동 승인 | 5천만 원 이하 + 3등급 이내 + DSR 30% 이하 |
| 2 | 본부 심사 필수 | 2억 초과 / 주담대 DSR 40% 초과 / 새희망홀씨 DSR 50% 초과 |
| 1 | 영업점장 전결 | 위 어디에도 해당하지 않음 |

### 2-5. 사용자 권한 확인

직급별 권한 레벨(행원 0, 지점장 1, 본부 2)과 필요한 레벨을 비교해 다음 중 하나를 알려줍니다.

- `[승인 가능]` 본인 전결 권한 내
- `[권한 부족]` 상위 결재 필요
- `[System Reject]` 규정상 취급 불가

### 출력 예시

연봉 6,000만 원, 신용 850점, 기존 상환 연 1,000만 원, 재직 4년, 신용대출 1억 원, 지점장 기준:

```json
{
  "css": {"total_score": 82.0, "grade": 2, "details": "신용(34.0) + 소득(18.0) + 거래(20) + 안정성(10)"},
  "dsr": {"current": 54.41, "stress": 56.27},
  "required_authority": "영업점장 전결 (Branch Manager)",
  "user_role_check": "[승인 가능] 귀하(manager)의 전결 권한 내입니다.",
  "risk_analysis": "금리 상승 시 DSR 규제(40%) 초과 위험"
}
```

## 3. 규정·상품 검색 (`regulatory_search`, RAG)

### 지식 베이스 구축

`python -m app.rag.vector_store` (`backend/`에서 실행) 시 기존 DB를 지우고 새로 만듭니다.

1. `backend/data/regulations/` 아래 `.pdf`, `.txt` 파일을 모두 읽습니다.
2. 폴더 이름으로 카테고리를 붙입니다.
   - `internal_rules` → `internal_rule`
   - `products` → `product`
   - `guidelines` → `guideline`
   - 그 외 → `general`
3. 1000자 단위, 200자 겹침으로 나눕니다.
4. 선택한 provider의 임베딩 모델로 임베딩해 ChromaDB(`backend/data/chromadb_storage/`)에 저장합니다.

### 검색

- 질문과 가장 비슷한 문서 조각 4개를 찾아 `[출처: 파일명]`과 함께 에이전트에 넘깁니다.
- 결과가 없으면 "관련된 규정이나 상품 정보를 찾을 수 없습니다."를 반환합니다.

### 수록 문서

| 카테고리 | 문서 |
|----------|------|
| 가이드라인 | 여신심사 선진화를 위한 가이드라인, 은행여신거래기본약관, 은행 가계대출 상품설명서 |
| 내부 규정 | 디디 내부심사규정 |
| 상품 | 디디 새희망홀씨2, 디디 자동차담보대출, 디디 주택담보대출, 디디 직장인대출(인터넷뱅킹) |

## 4. LLM Provider 선택

- 위치: `backend/app/llm_provider.py`
- `.env`의 `LLM_PROVIDER` 값으로 채팅 모델과 임베딩 모델을 함께 고릅니다. 기본값은 `gemini`입니다.

| `LLM_PROVIDER` | 채팅 모델 (기본값) | 임베딩 모델 (기본값) | 필요한 키 |
|------|------|------|------|
| `gemini` | `GEMINI_CHAT_MODEL` (`gemini-2.5-flash`) | `GEMINI_EMBEDDING_MODEL` (`models/gemini-embedding-001`) | `GOOGLE_API_KEY` |
| `openai` | `OPENAI_CHAT_MODEL` (`gpt-4o-mini`) | `OPENAI_EMBEDDING_MODEL` (`text-embedding-ada-002`) | `OPENAI_API_KEY` |

- `EMBEDDING_PROVIDER`를 따로 지정하면 임베딩만 다른 provider를 씁니다(예: 채팅은 Gemini, 임베딩은 OpenAI). 비워 두면 `LLM_PROVIDER`를 따라갑니다. 검색할 때도 벡터 DB를 만들 때와 같은 임베딩 provider를 써야 합니다.
- 벡터 DB를 만들 때 임베딩 요청을 `EMBED_BATCH_SIZE`개(기본 30)씩 나누고 묶음 사이에 `EMBED_BATCH_DELAY`초(기본 60)를 쉽니다. Gemini 무료 등급의 분당 한도 때문이며, 한도가 넉넉하면 0으로 둡니다.
- 목록에 없는 값이면 사용 가능한 provider 목록과 함께 오류를 냅니다.
- 새 provider는 `PROVIDERS`에 (채팅 모델, 임베딩) 생성 함수를 등록하면 추가됩니다.
- 임베딩 provider를 바꾸면 벡터 차원이 달라지므로 벡터 DB를 다시 만들어야 합니다.

## 5. 채팅 화면 (Frontend)

- 위치: `frontend/src/App.jsx` (React 17 + Vite, `@chatscope/chat-ui-kit-react`)
- 대화가 없을 때 추천 질문 카드 4개를 보여주고, 누르면 바로 질문이 전송됩니다.
  - 🔎 직장인 대출 한도 조회
  - 🧮 내 조건으로 심사 시뮬레이션
  - 🏠 주택담보대출 규제(LTV/DSR) 확인
  - ⚖️ 전결 규정 및 승인 권한 문의
- 답변을 기다리는 동안 "디디봇이 생각 중입니다..." 표시
- 서버 연결 실패 시 "⚠️ 서버 연결에 실패했습니다." 표시

## 6. API

### `POST /chat`

요청

```json
{
  "message": "연봉 6천, 신용 850점, 기존대출 1천만원 있어. 1억 대출 가능해?",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

응답

```json
{"response": "..."}
```
