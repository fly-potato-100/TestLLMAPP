import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');

  const handleSend = async () => {
    if (!input.trim()) return;
    
    // 添加用户消息
    const userMessage = { text: input, sender: 'user' };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    
    try {
      // 发送到后端代理
      const response = await axios.post(`${process.env.REACT_APP_API_BASE_URL}/chat`, {
        message: input
      });
      
      // 添加AI回复
      const aiMessage = { text: response.data.response, sender: 'ai' };
      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Error:', error);
      const errorMessage = { text: '发送消息失败', sender: 'error' };
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  return (
    <div className="app">
      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.sender}`}>
              {msg.text}
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
          <button onClick={handleSend}>发送</button>
        </div>
      </div>
    </div>
  );
}

export default App;
