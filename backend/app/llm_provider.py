# backend/app/llm_provider.py

import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_PROVIDER = "gemini"


def _openai_chat():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"), temperature=0)


def _openai_embeddings():
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings(model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"))


def _gemini_chat():
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash"), temperature=0)


def _gemini_embeddings():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    return GoogleGenerativeAIEmbeddings(model=os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001"))


# provider 추가 시 여기에 (채팅 모델, 임베딩) 생성 함수를 등록
PROVIDERS = {
    "openai": (_openai_chat, _openai_embeddings),
    "gemini": (_gemini_chat, _gemini_embeddings),
}


def get_provider_name():
    return (os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()


def get_embedding_provider_name():
    # 비어 있으면 LLM_PROVIDER를 따라감. 벡터 DB를 만든 provider와 같아야 검색이 동작함
    return (os.getenv("EMBEDDING_PROVIDER") or get_provider_name()).strip().lower()


def _get_factories(name, env_name):
    if name not in PROVIDERS:
        raise ValueError(f"지원하지 않는 {env_name}: '{name}' (사용 가능: {', '.join(PROVIDERS)})")
    return PROVIDERS[name]


def get_chat_model():
    return _get_factories(get_provider_name(), "LLM_PROVIDER")[0]()


def get_embeddings():
    return _get_factories(get_embedding_provider_name(), "EMBEDDING_PROVIDER")[1]()
