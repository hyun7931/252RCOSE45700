# backend/app/main.py

from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from app.rag.chatbot import route_message, get_form_response
from app.db.customer_repository import fetch_customer_profile, CustomerDBError
import uvicorn

app = FastAPI(title="DiDi Bank AI Underwriter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    history: list = []
    form_values: Optional[dict] = None  # 입력 폼 제출 시 심사 계산기 입력값

@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    if request.form_values is not None:
        return get_form_response(request.form_values, request.history)
    return route_message(request.message, request.history)

@app.get("/customers/{customer_id}")
def customer_endpoint(customer_id: str):
    """입력 폼의 '불러오기'용 고객 프로필"""
    try:
        profile = fetch_customer_profile(customer_id)
    except CustomerDBError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if profile is None:
        raise HTTPException(status_code=404, detail=f"고객 ID '{customer_id}'를 찾을 수 없습니다.")
    return profile

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
