# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

LIBO (Loan Intelligence Banking Officer) — a hybrid loan-underwriting assistant chatbot for a fictional bank "디디은행 (DiDi Bank)". It combines a **deterministic calculation engine** (DSR, CSS grade, approval authority, rate stress test) with **RAG over regulation/product documents** (ChromaDB), orchestrated by a LangChain tool-calling agent. The LLM/embedding provider (Gemini or OpenAI) is selected by `LLM_PROVIDER`. User-facing text, prompts, and data are in Korean.

## Commands

Backend (run from `backend/`; imports are `app.*`, so the working directory must be `backend/`). Requires `backend/.env` (copy from `backend/.env.example`): `LLM_PROVIDER` plus that provider's API key (`GOOGLE_API_KEY` or `OPENAI_API_KEY`). Use a Python 3.11 venv on Windows: `chroma-hnswlib` has no prebuilt 3.12 wheel there.

```bash
pip install -r requirements.txt
python -m app.rag.vector_store      # (re)build the vector DB — deletes and recreates data/chromadb_storage/
uvicorn app.main:app --reload --port 8000
python -m app.logic.loan_engine     # ad-hoc sanity check of the engine (manager vs hq authority)
python -m pytest                    # engine unit tests (tests/test_loan_engine.py)
python -m pytest tests/test_loan_engine.py::test_reject   # single test
docker build -t libo-backend . && docker run -p 8000:8000 --env-file .env libo-backend
```

Customer DB (Oracle XE in Docker; run from the repo root). `backend/.env` must define `DB_HOST`, `DB_PORT`, `DB_SERVICE`, `DB_USER`, `DB_PASSWORD`, `ORACLE_SYS_PASSWORD`:

```bash
docker compose --env-file backend/.env up -d oracle    # first start takes several minutes
backend/venv/Scripts/python scripts/init_data.py       # drops/recreates tables from scripts/schema.sql and seeds 100 customers (fixed seed)
```

The vector DB (`backend/data/chromadb_storage/`) is gitignored and must be built before the server can answer regulation questions. It is also baked into the Docker image only if it exists when building (it is not excluded by `.dockerignore`).

Frontend (run from `frontend/`):

```bash
npm install
npm run dev       # Vite dev server
npm run build
```

```bash
npm run lint      # ESLint 9 flat config (eslint.config.js)
```

Backend tests cover the engine (`tests/test_loan_engine.py`) and DB-row → engine-input conversion (`tests/test_customer_profile.py`); neither needs a database. There is no frontend test suite.

Feature documentation (Korean) lives in `docs/features.md`; keep it in sync when changing engine rules, tools, or the API.

## Architecture

Request flow: `frontend/src/App.jsx` → `POST /chat {message, history, form_values?}` → `backend/app/main.py` → `rag/chatbot.py:get_chatbot_response` → LangChain `AgentExecutor` → tools in `rag/tools.py` (`loan_calculator`, `regulatory_search`, `customer_lookup`).

- **Stateless chat**: the frontend keeps the full conversation and sends it as `history: [{role: "user"|"assistant", content}]` on every request; the backend converts it to `HumanMessage`/`AIMessage`. No server-side session.
- **System prompt** (`rag/chatbot.py`) defines the agent's behavior and requires a `[출처: ...]` citation at the end of every answer. For review requests the agent must call `loan_calculator` first even with partial inputs, rather than asking in prose; Gemini otherwise tends to skip the tool and ask directly, which suppresses the input form.
- **Input form flow** (#7): when required inputs are missing, `loan_calculator` returns `rag/form.py:missing_message` (`[필수 정보 누락]` + a `누락 항목:` code line). `get_chatbot_response` scans the agent's `intermediate_steps` and returns `{"response", "form": {"missing", "prefilled"}}`; the frontend (`LoanForm.jsx`) renders it inside the bot message. Form submissions come back as `/chat` `form_values`, and `get_form_response` calls `loan_calculator.invoke` directly and asks the LLM only to explain the result. `GET /customers/{id}` backs the form's 불러오기 button; the form omits loaded customer values the user did not edit so the backend uses the exact DB values (the form works in 만원 units).
- **`loan_calculator` tool** wraps `logic/loan_engine.py:LoanReviewEngine.run_simulation`. Required inputs are `loan_amount`, `annual_income`, `credit_score`, `current_annual_repayment`, job tenure (plus `collateral_value`/`region` for mortgages), all filled from the DB when `customer_id` is given. Optional inputs (`interest_rate` %, `term_years`, `stress_rate_increase` %p, `has_payroll`, `auto_transfers`) default to `None` so the tool can tell "not provided" apart; it then fills the `DEFAULT_*` constants in `tools.py` and lists them under `applied_conditions` → `기본값 적용 항목`, which the system prompt tells the agent to disclose. Percent inputs are converted to fractions before calling the engine. `user_role` (staff/manager/hq) defaults to `manager`.
- **`LoanReviewEngine`** encodes the internal rules from `data/regulations/internal_rules/디디 내부심사규정.txt`: CSS score (credit 40 + income 30 + transaction 20 + asset stability 10 → grade 1–15 via `GRADE_CUTOFFS`), DSR via level-payment amortization, credit-loan limit and cutoffs (job ≥ 24 months, grade < 9), mortgage LTV by region (`LTV_LIMITS`; `collateral_value` and `region` are required for `mortgage`, and the tool returns a `[필수 정보 누락]` string instead of calculating when they are missing), and approval authority levels (0 auto-approve / 1 branch manager / 2 HQ / 99 reject). Mortgage variable-rate stress / age limits, auto-loan collateral, and policy-loan detail rules are not implemented yet (issue #9). The regulation text was amended to fill gaps (score→grade table, 7–10 grade → HQ, DSR > 50% reject). If you change thresholds here, keep them consistent with that regulation text (and vice versa), since the RAG side cites the document while the engine computes the numbers.
- **Customer DB**: `app/db/customer_repository.py` queries Oracle (`python-oracledb` thin mode) and `app/logic/customer_profile.py:build_profile` turns rows into engine inputs (job months from `JOIN_DATE`, existing annual repayment by amortizing each loan's balance over its remaining months, unresolved delinquency count). When `loan_calculator` gets `customer_id`, it fills any input the user did not state from the profile (precedence: user value > DB value > `DEFAULT_*`), and returns `[고객 없음]` / `[DB 연결 실패]` strings instead of calculating on lookup failure. Unresolved delinquency is a reject reason in the engine. Demo customers `C2025_001`–`C2025_004` in `scripts/init_data.py` mirror the README scenarios.
- **`regulatory_search` tool** uses `rag/vector_store.py:get_retriever` (similarity, k=4). Indexing walks `backend/data/regulations/` recursively, loads `.pdf` (PyPDFLoader) and `.txt` (UTF-8 TextLoader), chunks 1000/200, embeds with the configured provider's embeddings, and stores `source_file` + `category` metadata. Category is derived from the folder name (`internal_rules`, `products`, `guidelines`, else `general`).
- **`app/llm_provider.py`** is the only place chat/embedding models are constructed. `get_chat_model()` dispatches on `LLM_PROVIDER` and `get_embeddings()` on `EMBEDDING_PROVIDER` (falls back to `LLM_PROVIDER`) via the `PROVIDERS` registry; model names come from `GEMINI_*` / `OPENAI_*` env vars. The embedding provider at query time must match the one that built the vector DB (dimensions differ); changing it requires a rebuild. Indexing embeds in batches (`EMBED_BATCH_SIZE`, `EMBED_BATCH_DELAY`) to stay under Gemini free-tier per-minute limits. `langchain-google-genai` is pinned to 2.0.7, the newest release compatible with `langchain-core==0.3.25`.
- `tools.py` instantiates the engine and retriever at import time, and `chatbot.py` silently falls back to `tools = []` on `ImportError`.

## Gotchas

- The frontend hardcodes the API URL `http://127.0.0.1:8000/chat` in `App.jsx`; change it for deployment (README demo used S3 for the frontend and EC2 for the backend).
- Frontend uses **React 17** (`ReactDOM.render`), not 18, so markdown libs are pinned to the unified-10 generation: `react-markdown@8`, `remark-gfm@3`, `rehype-raw@6`, `rehype-sanitize@5`. Newer majors require React 18. Bot messages render via chatscope `Message.CustomContent` inside `.markdown-body`; keep `rehype-sanitize` after `rehype-raw` since LLM/RAG output is untrusted.
- The root-level `package.json` is a stray dependency list; the real frontend project is `frontend/`.
- Docker Desktop on this machine has restarted mid-way through Oracle XE's first-time initialization (container exits with code 255 and an incomplete datafile volume). If that happens, remove the `oracle-data` volume and start again.
