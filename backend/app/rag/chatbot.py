from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.llm_provider import get_chat_model
from dotenv import load_dotenv
import json
import os

load_dotenv()

from app.rag.form import build_form, form_prompt

try:
    from app.rag.tools import tools, loan_calculator
except ImportError:
    print("경고 : Tools를 찾을 수 없습니다.")
    tools = []
    loan_calculator = None

llm = get_chat_model()

SYSTEM_PROMPT = """
    당신은 '디디은행'의 베테랑 여신 심사역 보조 AI, '디디 봇'입니다.
    당신의 목표는 심사역(사용자)이 고객의 대출 가능 여부를 판단할 때 정확한 근거와 데이터를 제공하는 것입니다.

    [행동 수칙]
    1. **필수 정보 확인**: 심사(계산)에는 다음 정보가 필요합니다.
       - 연소득, 신용점수, 기존 대출 상환액, 대출 신청 금액, **재직 기간**, **원하는 상품 종류(신용/담보 등)**
       - 주택담보대출이면 **담보 주택 가액**과 **지역 구분(투기과열지구/조정대상지역/일반지역)**도 필요합니다. 투기과열지구면 실수요자 여부도 물어보세요.
       - **대출 가능 여부·심사·한도 계산 요청이면, 정보가 부족해도 직접 되묻지 말고 반드시 먼저 loan_calculator를 호출하세요.** 아는 값만 넣고 나머지는 비워서 호출하면 됩니다. 도구를 호출하지 않고 정보를 요청하는 답변은 금지입니다.
       - 도구가 '[필수 정보 누락]'을 반환하면 계산 결과를 지어내지 말고, 빠진 항목을 짧게 안내하세요. 화면에 입력 폼이 함께 표시되므로 "아래 입력 폼에 입력해 주세요"라고 안내하세요.
       - **고객 ID(예: C2025_001)가 주어지면** 연소득·신용점수·기존 대출·재직 기간·자산·급여이체·자동이체는 묻지 말고, loan_calculator에 customer_id를 넣어 고객 DB 값으로 계산하세요. 대출 신청 금액과 상품 종류(주택담보대출이면 담보 정보)만 확인하면 됩니다.
       - 고객 정보·기존 대출·연체 이력 조회는 'customer_lookup' 도구를 사용하세요. '[고객 없음]'이나 '[DB 연결 실패]'가 반환되면 그대로 안내하세요.
    2. **수치 계산**: 'loan_calculator' 도구로 DSR과 등급을 계산하세요.
       - 금리, 대출 기간, 급여이체 여부, 자동이체 건수, 보유 자산, 금리 상승폭은 사용자가 말한 경우에만 도구에 넣고, 말하지 않았으면 비워두세요. (임의로 추정하지 마세요)
       - "금리가 3% 오르면?"처럼 금리 상승을 물으면 이전 대화의 고객 정보에 stress_rate_increase를 넣어 다시 계산하세요.
       - 결과의 applied_conditions에 '기본값 적용 항목'이 있으면, 답변에 어떤 기본값으로 계산했는지 밝히고 실제 값을 알려주면 다시 계산할 수 있다고 안내하세요.
    3. **규정 검색**: 상품의 세부 조건(금리, 한도 등)은 'regulatory_search' 도구로 확인하세요.
    4. **출처 명시**: 답변의 끝은 항상 정보의 출처를 명시하세요. (출처 : 파일명, 규정 조항, 또는 '심사 엔진 결과' 등)
        - 예시 : [출처: 디디 내부심사규정.txt 12p] / [출처: 여신심사 선진화를 위한 가이드라인.txt 10p] / [출처: 내부 심사 엔진 결과]
    """

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, return_intermediate_steps=True)

ERROR_MESSAGE = "내부 시스템 오류로 답변을 생성할 수 없습니다."


def format_history(chat_history: list):
    formatted_history = []
    for msg in chat_history:
        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                formatted_history.append(HumanMessage(content=content))
            elif role == "assistant":
                formatted_history.append(AIMessage(content=content))
    return formatted_history


def get_chatbot_response(user_input: str, chat_history: list):
    """일반 채팅. {"response": 답변, "form": 입력 폼 정보 또는 None}"""
    try:
        response = agent_executor.invoke({
            "input": user_input,
            "chat_history": format_history(chat_history)
        })
    except Exception as e:
        print(f"에이전트 실행 중 오류: {e}")
        return {"response": ERROR_MESSAGE, "form": None}

    # 마지막 계산기 호출이 필수 정보 누락이면 입력 폼을 함께 보냄
    form = None
    for action, observation in response.get("intermediate_steps", []):
        if action.tool == "loan_calculator":
            form = build_form(observation, action.tool_input)
    return {"response": response["output"], "form": form}


def get_form_response(form_values: dict, chat_history: list):
    """입력 폼 제출. 계산은 심사 엔진이 직접 하고, LLM은 결과 설명만 함"""
    values = {k: v for k, v in form_values.items() if v is not None and v != ""}
    try:
        result = loan_calculator.invoke(values)
    except Exception as e:
        print(f"입력 폼 계산 중 오류: {e}")
        return {"response": f"입력값을 확인해 주세요: {e}", "form": {"missing": [], "prefilled": values}}

    form = build_form(result, values)
    if form is not None:
        return {"response": form_prompt(form["missing"]), "form": form}
    if isinstance(result, str):
        return {"response": result, "form": None}

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        *format_history(chat_history),
        HumanMessage(content=(
            "심사역이 입력 폼으로 아래 조건을 제출했고, 심사 엔진(loan_calculator)이 계산한 결과는 다음과 같습니다.\n"
            "이 결과만 근거로 심사 결과를 설명하세요. 숫자를 바꾸거나 다시 계산하지 마세요. "
            "기본값 적용 항목이 있으면 안내하고, 끝에 [출처: 내부 심사 엔진 결과]를 붙이세요.\n\n"
            f"[입력 조건]\n{json.dumps(values, ensure_ascii=False)}\n\n"
            f"[심사 엔진 결과]\n{json.dumps(result, ensure_ascii=False)}"
        )),
    ]
    try:
        answer = llm.invoke(messages).content
    except Exception as e:
        print(f"결과 설명 생성 중 오류: {e}")
        return {"response": ERROR_MESSAGE, "form": None}
    return {"response": answer, "form": None}
