// frontend/src/App.jsx
import React, { useState } from 'react';
import axios from 'axios';
import '@chatscope/chat-ui-kit-styles/dist/default/styles.min.css';
import {
  MainContainer,
  ChatContainer,
  MessageList,
  Message,
  MessageInput,
  TypingIndicator
} from '@chatscope/chat-ui-kit-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import LoanForm from './LoanForm.jsx';
import './index.css';

const API_BASE = "http://127.0.0.1:8000";

const OPEN_FORM_MESSAGE = "아래 입력 폼에 심사할 조건을 입력해 주세요. 고객 ID가 있으면 **불러오기**로 고객 정보를 채울 수 있습니다.";

function App() {
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  // 직전 계산 조건: 서버가 돌려준 값을 보관했다가 다음 요청에 보냄 (후속 질문 재계산, 폼 미리 채우기)
  const [lastInputs, setLastInputs] = useState(null);

  const botMessage = (text, form = null) => ({
    message: text,
    sender: "system",
    direction: "incoming",
    form,
    formSubmitted: false
  });

  // message: 화면에 보일 사용자 메시지 / formValues: 입력 폼 제출 값 (있으면 백엔드가 계산기를 직접 호출)
  const sendToServer = async (message, formValues = null, baseMessages = messages) => {
    const newMessages = [...baseMessages, { message, sender: "user", direction: "outgoing" }];
    setMessages(newMessages);
    setIsTyping(true);

    const historyPayload = baseMessages.map((msg) => ({
      role: msg.sender === "user" ? "user" : "assistant",
      content: msg.message
    }));

    try {
      const response = await axios.post(`${API_BASE}/chat`, {
        message: message,
        history: historyPayload,
        form_values: formValues,
        last_inputs: lastInputs
      });
      if (response.data.last_inputs) setLastInputs(response.data.last_inputs);
      setMessages([...newMessages, botMessage(response.data.response, response.data.form)]);
    } catch {
      setMessages([...newMessages, botMessage("⚠️ 서버 연결에 실패했습니다.")]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSend = (message) => sendToServer(message);

  const handleFormSubmit = (index) => (payload, summary) => {
    const updated = messages.map((msg, i) => (i === index ? { ...msg, formSubmitted: true } : msg));
    sendToServer(summary, payload, updated);
  };

  const openForm = () => {
    setMessages([...messages, botMessage(OPEN_FORM_MESSAGE, { missing: [], prefilled: lastInputs || {} })]);
  };

  const suggestionCards = [
    {
      title: "🧮 직접 입력해서 심사",
      action: openForm
    },
    {
      title: "🔎 직장인 대출 한도 조회",
      query: "연봉 5천만원 직장인인데, 신용대출 최대한도가 얼마야?"
    },
    {
      title: "👤 고객 ID로 심사 시뮬레이션",
      query: "C2025_001 고객 직장인 신용대출 1억, 금리 5%, 5년 심사해줘"
    },
    {
      title: "🏠 주택담보대출 규제(LTV/DSR) 확인",
      query: "투기과열지구 주택담보대출 LTV랑 DSR 한도가 어떻게 돼?"
    },
    {
      title: "⚖️ 전결 규정 및 승인 권한 문의",
      query: "대출 금액이 얼마를 넘으면 본부 심사로 넘어가?"
    }
  ];

  return (
    <div className="app-container">
      <div className="chat-title">DD Chatbot</div>
      <MainContainer>
        <ChatContainer>
          <MessageList
            typingIndicator={isTyping ? <TypingIndicator content="디디봇이 생각 중입니다..." /> : null}
          >
            {/* --- 랜딩 페이지 (대화 없을 때) --- */}
            {messages.length === 0 && (
              <div className="landing-container">
                <div className="landing-header">
                  <div className="landing-icon">🏦</div>
                  <h2>무엇을 도와드릴까요?</h2>
                </div>

                <div className="suggestion-section">
                  <p className="suggestion-label">이런 질문이 가능해요!</p>
                  <div className="suggestion-list">
                    {suggestionCards.map((card, index) => (
                      <button
                        key={index}
                        className="suggestion-btn"
                        onClick={() => (card.action ? card.action() : handleSend(card.query))}
                      >
                        {card.title}
                        <span className="arrow-icon">→</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* --- 실제 채팅 대화 --- */}
            {messages.map((msg, i) => (
              msg.direction === "incoming" ? (
                <Message key={i} model={{ ...msg, type: "custom" }}>
                  <Message.CustomContent>
                    <div className="markdown-body">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw, rehypeSanitize]}>{msg.message}</ReactMarkdown>
                    </div>
                    {msg.form && (
                      <LoanForm
                        apiBase={API_BASE}
                        form={msg.form}
                        disabled={msg.formSubmitted || isTyping}
                        onSubmit={handleFormSubmit(i)}
                      />
                    )}
                  </Message.CustomContent>
                </Message>
              ) : (
                <Message key={i} model={msg} />
              )
            ))}
          </MessageList>

          <MessageInput
            placeholder="디디봇에게 무엇이든 물어보세요..."
            onSend={handleSend}
            attachButton={false}
          />

        </ChatContainer>
      </MainContainer>
    </div>
  );
}

export default App;
