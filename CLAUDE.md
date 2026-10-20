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

Only the backend engine has tests; there is no frontend test suite.

Feature documentation (Korean) lives in `docs/features.md`; keep it in sync when changing engine rules, tools, or the API.

## Architecture

Request flow: `frontend/src/App.jsx` → `POST /chat {message, history}` → `backend/app/main.py` → `rag/chatbot.py:get_chatbot_response` → LangChain `AgentExecutor` → one of two tools in `rag/tools.py`.

- **Stateless chat**: the frontend keeps the full conversation and sends it as `history: [{role: "user"|"assistant", content}]` on every request; the backend converts it to `HumanMessage`/`AIMessage`. No server-side session.
- **System prompt** (`rag/chatbot.py`) defines the agent's behavior: ask for missing inputs (income, credit score, existing repayment, loan amount, job years, product type) before calling the calculator, and always end answers with a `[출처: ...]` citation.
- **`loan_calculator` tool** wraps `logic/loan_engine.py:LoanReviewEngine.run_simulation`. Optional inputs (`interest_rate` %, `term_years`, `stress_rate_increase` %p, `has_payroll`, `auto_transfers`) default to `None` so the tool can tell "not provided" apart; it then fills the `DEFAULT_*` constants in `tools.py` and lists them under `applied_conditions` → `기본값 적용 항목`, which the system prompt tells the agent to disclose. Percent inputs are converted to fractions before calling the engine. `user_role` (staff/manager/hq) defaults to `manager`.
- **`LoanReviewEngine`** encodes the internal rules from `data/regulations/internal_rules/디디 내부심사규정.txt`: CSS score (credit 40 + income 30 + transaction 20 + asset stability 10 → grade 1–15 via `GRADE_CUTOFFS`), DSR via level-payment amortization, credit-loan limit and cutoffs (job ≥ 24 months, grade < 9), and approval authority levels (0 auto-approve / 1 branch manager / 2 HQ / 99 reject). Collateral (LTV, vehicle) and policy-loan detail rules are not implemented yet (issue #9). The regulation text was amended to fill gaps (score→grade table, 7–10 grade → HQ, DSR > 50% reject). If you change thresholds here, keep them consistent with that regulation text (and vice versa), since the RAG side cites the document while the engine computes the numbers.
- **`regulatory_search` tool** uses `rag/vector_store.py:get_retriever` (similarity, k=4). Indexing walks `backend/data/regulations/` recursively, loads `.pdf` (PyPDFLoader) and `.txt` (UTF-8 TextLoader), chunks 1000/200, embeds with the configured provider's embeddings, and stores `source_file` + `category` metadata. Category is derived from the folder name (`internal_rules`, `products`, `guidelines`, else `general`).
- **`app/llm_provider.py`** is the only place chat/embedding models are constructed. `get_chat_model()` dispatches on `LLM_PROVIDER` and `get_embeddings()` on `EMBEDDING_PROVIDER` (falls back to `LLM_PROVIDER`) via the `PROVIDERS` registry; model names come from `GEMINI_*` / `OPENAI_*` env vars. The embedding provider at query time must match the one that built the vector DB (dimensions differ); changing it requires a rebuild. Indexing embeds in batches (`EMBED_BATCH_SIZE`, `EMBED_BATCH_DELAY`) to stay under Gemini free-tier per-minute limits. `langchain-google-genai` is pinned to 2.0.7, the newest release compatible with `langchain-core==0.3.25`.
- `tools.py` instantiates the engine and retriever at import time, and `chatbot.py` silently falls back to `tools = []` on `ImportError`.

## Gotchas

- The frontend hardcodes the API URL `http://127.0.0.1:8000/chat` in `App.jsx`; change it for deployment (README demo used S3 for the frontend and EC2 for the backend).
- Frontend uses **React 17** (`ReactDOM.render`), not 18, so markdown libs are pinned to the unified-10 generation: `react-markdown@8`, `remark-gfm@3`, `rehype-raw@6`, `rehype-sanitize@5`. Newer majors require React 18. Bot messages render via chatscope `Message.CustomContent` inside `.markdown-body`; keep `rehype-sanitize` after `rehype-raw` since LLM/RAG output is untrusted.
- The root-level `package.json` is a stray dependency list; the real frontend project is `frontend/`.
- `scripts/init_data.py` seeds a local Oracle XE DB (`CUSTOMERS`, `LOAN_ACCOUNTS`, `DELINQUENCY_HISTORY`) with Faker data, but Oracle is not wired into the backend yet (`oracledb` is commented out in `requirements.txt`); it is listed as a TODO in the README.
