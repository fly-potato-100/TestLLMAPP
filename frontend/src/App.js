import React, { useState } from 'react';
import axios from 'axios';
import './App.css';
import CONFIG from "./config";

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');

  const handleSend = async () => {
    if (!input.trim()) return;
    
    // 添加用户消息
    const userMessage = { text: input, sender: 'user', time: new Date().toLocaleTimeString() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    
    try {
      // 发送到后端代理
      const response = await axios.post(`${CONFIG.API_BASE_URL}/chat`, {
        message: input
      });
      
      // 添加AI回复
      const aiMessage = { text: response.data.response, sender: 'ai', time: new Date().toLocaleTimeString() };
      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Error:', error);
      const errorMessage = { text: '发送消息失败', sender: 'error', time: new Date().toLocaleTimeString() };
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  return (
    <div className="app">
      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, index) => (
            <div key={index} className={`message-row ${msg.sender}`}> 
              {msg.sender === 'ai' && <div className="avatar ai-avatar">🤖</div>}
              {msg.sender === 'error' && <div className="avatar error-avatar">⚠️</div>}
              <div className={`message ${msg.sender}`}>
                {msg.text}
                <div className="timestamp">{msg.time}</div>
              </div>
              {msg.sender === 'user' && <div className="avatar user-avatar">🧑</div>}
            </div>
          ))}
        </div>
        <div className="input-area">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder="输入消息..."
          />
          <button className="send-btn" onClick={handleSend} aria-label="发送">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2 21L23 12L2 3V10L17 12L2 14V21Z" fill="currentColor"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
