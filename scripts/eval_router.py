# scripts/eval_router.py
# 라우터 분류 정확도 평가: backend/tests/data/router_cases.json의 질문을 실제 LLM으로 분류
# 실행 (저장소 루트에서): backend/venv/Scripts/python scripts/eval_router.py
# 질문마다 LLM을 1회 호출하므로 무료 한도에 주의 (LLM_PROVIDER=openai 등으로 바꿔 실행 가능)

import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT / "backend")
sys.path.insert(0, str(ROOT / "backend"))

from app.llm_provider import get_chat_model, get_provider_name  # noqa: E402
from app.rag.router import rule_route, llm_route  # noqa: E402


def main():
    cases = json.loads((ROOT / "backend" / "tests" / "data" / "router_cases.json").read_text(encoding="utf-8"))
    llm = get_chat_model()
    correct, confusion, llm_calls = 0, Counter(), 0

    for case in cases:
        predicted = rule_route(case["message"])
        source = "규칙"
        if predicted is None:
            try:
                predicted = llm_route(llm, case["message"], case.get("history", [])).intent
            except Exception as e:
                predicted = f"error({type(e).__name__})"
            source = "LLM"
            llm_calls += 1
        ok = predicted == case["intent"]
        correct += ok
        confusion[(case["intent"], predicted)] += 1
        print(f"{'✅' if ok else '❌'} [{source}] 기대 {case['intent']:<10} 예측 {predicted:<10} | {case['message']}")

    print(f"\n모델: {get_provider_name()} / 정확도 {correct}/{len(cases)} ({correct / len(cases):.0%}) / LLM 호출 {llm_calls}회")
    wrong = {k: v for k, v in confusion.items() if k[0] != k[1]}
    if wrong:
        print("오분류:", ", ".join(f"{e}→{p} {n}건" for (e, p), n in wrong.items()))


if __name__ == "__main__":
    main()
