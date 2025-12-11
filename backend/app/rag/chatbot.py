from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv
import os

load_dotenv()

try:
    from app.rag.tools import tools
except ImportError:
    print("경고 : Tools를 찾을 수 없습니다.")
    tools = []

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", """
    당신은 '디디은행'의 베테랑 여신 심사역 보조 AI, '디디 봇'입니다.
    당신의 목표는 심사역(사용자)이 고객의 대출 가능 여부를 판단할 때 정확한 근거와 데이터를 제공하는 것입니다.

    [행동 수칙]
    1. **필수 정보 확인**: 심사(계산)를 하려면 반드시 다음 5가지 정보가 필요합니다. 누락된 정보가 있다면 사용자에게 먼저 물어보세요.
       - 연소득, 신용점수, 기존 대출 상환액, 대출 신청 금액, **재직 기간**, **원하는 상품 종류(신용/담보 등)**
    2. **수치 계산**: 모든 정보가 모이면 'loan_calculator' 도구를 사용하여 DSR과 등급을 계산하세요.
    3. **규정 검색**: 상품의 세부 조건(금리, 한도 등)은 'regulatory_search' 도구로 확인하세요.
    4. **출처 명시**: 답변의 끝은 항상 정보의 출처를 명시하세요. (출처 : 파일명, 규정 조항, 또는 '심사 엔진 결과' 등)
        - 예시 : [출처: 디디 내부심사규정.txt 12p] / [출처: 여신심사 선진화를 위한 가이드라인.txt 10p] / [출처: 내부 심사 엔진 결과]
    """),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

def get_chatbot_response(user_input: str, chat_history: list):
    formatted_history = []
    for msg in chat_history:
        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                formatted_history.append(HumanMessage(content=content))
            elif role == "assistant":
                formatted_history.append(AIMessage(content=content))
    
    try:
        response = agent_executor.invoke({
            "input": user_input,
            "chat_history": formatted_history
        })
        return response["output"]
        
    except Exception as e:
        print(f"에이전트 실행 중 오류: {e}")
        return "내부 시스템 오류로 답변을 생성할 수 없습니다."