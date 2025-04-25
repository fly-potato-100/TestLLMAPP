import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';
import CONFIG from "./config";

// 新增：会话信息控件组件
function SessionInfo({ sessionId, usages }) {
  const [isExpanded, setIsExpanded] = useState(false);

  // 如果既没有 sessionId 也没有 usage.models，则不渲染
  if (!sessionId && (!usages || !usages.models || usages.models.length === 0)) {
    return null;
  }

  return (
    <div className="session-info-container">
      <span className="session-toggle-icon" onClick={() => setIsExpanded(!isExpanded)}>
        {isExpanded ? '▲' : '▼'}
      </span>
      {isExpanded && (
        <div className="session-details-bubble">
          {sessionId && <div className="session-id-info">SessionID: {sessionId}</div>}

          {usages?.models?.map((model, index) => {
            const inputTokens = model.input_tokens ?? 0; // 使用 ?? 提供默认值 0
            const outputTokens = model.output_tokens ?? 0;
            const totalTokens = inputTokens + outputTokens;
            return (
              <div key={index} className="usage-model-info">
                {`Model${index + 1}: ${model.model_id || 'N/A'}; Input: ${inputTokens}; Output: ${outputTokens}; Total: ${totalTokens}`}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// 新增：候选答案组件展示
function CandidateAnswers({ answers, selectedIndex, onSelect, groupName }) {
  if (!answers || answers.length === 0) return null;
  return (
    <div className="candidate-answers">
      <div className="candidate-title">候选答案：</div>
      <table className="candidate-table">
        <thead>
          <tr>
            <th className="col-select">选择</th>
            <th className="col-score">分数</th>
            <th className="col-answer">答案</th>
            <th className="col-reason">原因</th>
          </tr>
        </thead>
        <tbody>
          {answers.map((item, index) => (
            <tr key={index} className={index === selectedIndex ? 'selected' : ''}>
              <td>
                <input
                  type="radio"
                  name={groupName}
                  checked={index === selectedIndex}
                  onChange={() => onSelect(index)}
                />
              </td>
              <td className="candidate-score">
                {((item.score || 0) * 100).toFixed(1)}%
              </td>
              <td className="candidate-text">
                {item.content}
              </td>
              <td className="candidate-reason">
                {item.reason || '-'} {/* 如果没有 reason，显示 '-' */}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [channelName, setChannelName] = useState('官方');
  const [platformName, setPlatformName] = useState('android');
  const [serviceName, setServiceName] = useState('agent');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // 处理切换候选答案
  const handleSelectCandidate = (msgIndex, newIndex) => {
    setMessages(prev =>
      prev.map((m, i) => {
        if (i === msgIndex && m.sender === 'ai') {
          return {
            ...m,
            selectedIndex: newIndex,
            text: m.candidateAnswers[newIndex]?.content || m.text,
          };
        }
        return m;
      })
    );
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = { text: input, sender: 'user', time: new Date().toLocaleTimeString() };
    const currentInput = input;
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // 准备符合 API 格式的消息历史
      const historyMessages = messages
        .filter(msg => msg.sender !== 'error') // 过滤掉错误消息
        .map(msg => ({
          role: msg.sender === 'user' ? 'user' : 'assistant',
          content: msg.text
        }));

      // 添加当前用户输入的消息
      historyMessages.push({ role: 'user', content: currentInput });

      // 发送到后端代理
      const url = `${CONFIG.API_BASE_URL}/chat`;
      // 修改 requestData 结构，添加 service_name
      const requestData = {
        conversation: historyMessages, // 使用格式化后的历史消息和当前输入
        session_id: currentSessionId, // 发送当前 sessionId
        service: serviceName, // 将 service 移到顶层
        context_params: {
          channel_name: channelName,
          platform_name: platformName,
          // service: serviceName, // 从这里移除
        }
      };
      console.log('Sending request to:', url);
      console.log('Request data:', requestData);
      // 发送当前 session_id 到后端
      const response = await axios.post(url, requestData);
      console.log('Received response:', response.data);

      // --- 处理 AI 回复 (统一按 JSON 候选答案格式处理) --- 
      let aiResponseText = '抱歉，未能获取到回复。';
      let candidates = [];
      let selectedIndex = 0;

      const rawResponse = response.data.response_text;

      try {
        // 始终尝试将 response_text 解析为 JSON 数组 (候选答案列表)
        candidates = JSON.parse(rawResponse);
        // 如果解析成功且是包含内容的数组，取第一个作为默认回复
        aiResponseText = candidates[0].content; // 添加空检查
        selectedIndex = 0;

      } catch (e) {
        // 如果 JSON 解析失败，说明返回的不是预期的 JSON 格式，直接将原始文本作为回复
        throw new Error("后台报错:" + rawResponse);
      }

      const aiMessage = {
        text: aiResponseText,
        candidateAnswers: candidates, // 传递解析后的候选答案列表
        selectedIndex: selectedIndex,
        sender: 'ai',
        time: new Date().toLocaleTimeString(),
        sessionId: response.data.session_id,
        usages: response.data.usages
      };
      // --- 处理结束 ---

      console.log('AI message:', aiMessage);

      setMessages(prev => [...prev, aiMessage]);
      // 更新当前 session_id 以备下次请求使用
      setCurrentSessionId(response.data.session_id);

    } catch (error) {
      console.error('Error sending message:', error);
      
      // 使用函数式更新
      const errorMessage = { 
          text: `${error.response?.data?.error || error.message || '未知错误'}`, 
          sender: 'error', 
          time: new Date().toLocaleTimeString() 
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // 新增：清空聊天记录和会话状态的函数
  const handleClear = () => {
    setMessages([]);
    setCurrentSessionId(null);
  };

  return (
    <div className="app">
      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, index) => (
            <div key={index} className={`message-row ${msg.sender}`}>
              {msg.sender === 'ai' && (
                <>
                  <div className="avatar ai-avatar">🤖</div>
                  <div className="message-content-wrapper">
                    <div className={`message ${msg.sender}`}>{msg.text}</div>
                    <CandidateAnswers
                      answers={msg.candidateAnswers}
                      selectedIndex={msg.selectedIndex}
                      onSelect={newIdx => handleSelectCandidate(index, newIdx)}
                      groupName={`candidate-${index}`}
                    />
                    <div className="message-footer">
                      <SessionInfo sessionId={msg.sessionId} usages={msg.usages} />
                      <div className="timestamp">{msg.time}</div>
                    </div>
                  </div>
                </>
              )}
              {msg.sender === 'error' && (
                <>
                  <div className="avatar error-avatar">⚠️</div>
                  <div className="message-content-wrapper">
                    <div className={`message ${msg.sender}`}>{msg.text}</div>
                  </div>
                </>
              )}
              {msg.sender === 'user' && (
                <>
                  <div className="avatar user-avatar">🧑</div>
                  <div className="message-content-wrapper user">
                    <div className={`message ${msg.sender}`}>{msg.text}</div>
                    <div className="message-footer user">
                        <div className="timestamp">{msg.time}</div>
                    </div>
                  </div>
                </>
              )}
            </div>
          ))}
          {isLoading && (
            <div className="message-row ai">
              <div className="avatar ai-avatar">⏳</div>
              <div className="message-content-wrapper">
                <div className="message ai loading-dots">
                  <span>.</span><span>.</span><span>.</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <div className="biz-params-selectors">
          <label>
            渠道:
            <select value={channelName} onChange={(e) => setChannelName(e.target.value)} disabled={isLoading}>
              <option value="小米">小米</option>
              <option value="华为">华为</option>
              <option value="苹果">苹果</option>
              <option value="官方">官方</option>
              <option value="祖龙">祖龙</option>
            </select>
          </label>
          <label>
            平台:
            <select value={platformName} onChange={(e) => setPlatformName(e.target.value)} disabled={isLoading}>
              <option value="android">Android</option>
              <option value="ios">iOS</option>
              <option value="web">Web</option>
              <option value="pc">PC</option>
            </select>
          </label>
        </div>
        <div className="input-area">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder="输入消息..."
            disabled={isLoading}
          />
          <div className="send-service-group">
            <button className="send-btn" onClick={handleSend} aria-label="发送" disabled={isLoading}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2 21L23 12L2 3V10L17 12L2 14V21Z" fill="currentColor"/></svg>
            </button>
            <select className="service-select" value={serviceName} onChange={(e) => setServiceName(e.target.value)} disabled={isLoading}>
              <option value="bailian">Bailian</option>
              <option value="coze">Coze</option>
              <option value="agent">Agent</option>
            </select>
          </div>
          <button className="clear-btn" onClick={handleClear} aria-label="清空" disabled={isLoading}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path fillRule="evenodd" clipRule="evenodd" d="M6 5C5.44772 5 5 5.44772 5 6V7H4C3.44772 7 3 7.44772 3 8C3 8.55228 3.44772 9 4 9H5V18C5 19.6569 6.34315 21 8 21H16C17.6569 21 19 19.6569 19 18V9H20C20.5523 9 21 8.55228 21 8C21 7.44772 20.5523 7 20 7H19V6C19 5.44772 18.5523 5 18 5C17.4477 5 17 5.44772 17 6V7H7V6C7 5.44772 6.55228 5 6 5ZM8 9H16V18C16 18.5523 15.5523 19 15 19H9C8.44772 19 8 18.5523 8 18V9ZM11 11C10.4477 11 10 11.4477 10 12V16C10 16.5523 10.4477 17 11 17C11.5523 17 12 16.5523 12 16V12C12 11.4477 11.5523 11 11 11ZM14 11C13.4477 11 13 11.4477 13 12V16C13 16.5523 13.4477 17 14 17C14.5523 17 15 16.5523 15 16V12C15 11.4477 14.5523 11 14 11Z" fill="currentColor"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
