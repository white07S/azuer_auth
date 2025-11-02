import React, { useState, useEffect, useRef } from 'react';
import { Send, Loader, AlertCircle } from 'lucide-react';
import MessageList from './MessageList';
import { chatAPI } from '../api';

const ChatInterface = ({ sessionId, roles = [] }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }

    const loadChatHistory = async () => {
      try {
        const history = await chatAPI.getChatHistory(sessionId);
        setMessages(history || []);
      } catch (err) {
        console.error('Failed to load chat history:', err);
      }
    };

    loadChatHistory();
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const generateMessageId = () => `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) {
      return;
    }

    if (!sessionId) {
      setError('Session is not ready. Please sign in again.');
      return;
    }

    const userMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString(),
      id: generateMessageId(),
    };

    const recentContext = [...messages, userMessage].slice(-10);

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setError(null);

    try {
      const response = await chatAPI.sendMessage(sessionId, userMessage.content, recentContext);
      const aiMessage = {
        role: 'assistant',
        content: response.message,
        timestamp: response.timestamp,
        id: generateMessageId(),
      };
      setMessages(prev => [...prev, aiMessage]);
    } catch (err) {
      console.error('Failed to send message:', err);
      setError('Failed to send message. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  const clearChat = async () => {
    if (!sessionId) {
      return;
    }
    if (!roles.includes('admin')) {
      setError('You do not have permission to clear chat history.');
      return;
    }

    try {
      await chatAPI.clearChatHistory(sessionId);
      setMessages([]);
      setError(null);
    } catch (err) {
      console.error('Failed to clear chat history:', err);
      setError('Could not clear chat history.');
    }
  };

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <h2>AI Assistant</h2>
        <div className="chat-status">
          <span className="status-indicator connected"></span>
          <span>Session active</span>
        </div>
      </div>

      <div className="chat-messages">
        <MessageList messages={messages} isLoading={isLoading} />
        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="chat-error">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="chat-input-container">
        <div className="chat-input-wrapper">
          <textarea
            value={inputMessage}
            onChange={(event) => setInputMessage(event.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message here..."
            className="chat-input"
            rows="3"
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!inputMessage.trim() || isLoading}
            className="btn-send"
          >
            {isLoading ? <Loader size={20} className="spinner" /> : <Send size={20} />}
          </button>
        </div>
        {roles.includes('admin') && (
          <div className="chat-actions">
            <button onClick={clearChat} className="btn-text">
              Clear Chat
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatInterface;
