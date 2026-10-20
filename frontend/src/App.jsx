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
import './index.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);

  const handleSend = async (message) => {
    const newUserMessage = {
      message: message,
      sender: "user",
      direction: "outgoing"
    };

    const newMessages = [...messages, newUserMessage];
    setMessages(newMessages);
    setIsTyping(true);

    const historyPayload = messages.map((msg) => ({
      role: msg.sender === "user" ? "user" : "assistant",
      content: msg.message
    }));

    try {
      const response = await axios.post("http://127.0.0.1:8000/chat", {
        message: message,
        history: historyPayload
      });

      const newBotMessage = {
        message: response.data.response,
        sender: "system",
        direction: "incoming"
      };
      
      setMessages([...newMessages, newBotMessage]);
      
    } catch {
      const errorMessage = {
        message: "⚠️ 서버 연결에 실패했습니다.",
        sender: "system",
        direction: "incoming"
      };
      setMessages([...newMessages, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const suggestionCards = [
    {
      title: "🔎 직장인 대출 한도 조회",
      query: "연봉 5천만원 직장인인데, 신용대출 최대한도가 얼마야?"
    },
    {
      title: "🧮 내 조건으로 심사 시뮬레이션",
      query: "연봉 8천, 신용 900점, 재직 3년 6개월 직장인이야. 기존 상환 연 500만 원, 급여이체·자동이체 3건 있고 자산 3억. 금리 5%, 5년으로 직장인 신용대출 1억 가능해?"
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
                        onClick={() => handleSend(card.query)}
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