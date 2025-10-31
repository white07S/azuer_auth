import React, { useState, useEffect, useRef } from 'react';
import { Send, Loader, AlertCircle } from 'lucide-react';
import MessageList from './MessageList';
import { chatAPI } from '../utils/api';

const ChatInterface = ({ sessionId }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    // Connect to WebSocket
    connectWebSocket();

    // Load chat history
    loadChatHistory();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [sessionId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const connectWebSocket = () => {
    const wsUrl = `ws://localhost:8000/ws/${sessionId}`;
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      setError(null);
    };

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'response') {
          const aiMessage = {
            role: 'assistant',
            content: data.data.message,
            timestamp: data.data.timestamp,
            id: generateMessageId()
          };
          setMessages(prev => [...prev, aiMessage]);
          setIsLoading(false);
        } else if (data.type === 'error') {
          setError(data.message);
          setIsLoading(false);
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setError('Connection error. Please refresh the page.');
      setIsConnected(false);
    };

    wsRef.current.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);

      // Attempt to reconnect after 3 seconds
      setTimeout(() => {
        if (sessionId) {
          connectWebSocket();
        }
      }, 3000);
    };
  };

  const loadChatHistory = async () => {
    try {
      const history = await chatAPI.getChatHistory(sessionId);
      setMessages(history || []);
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const generateMessageId = () => {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString(),
      id: generateMessageId()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setError(null);

    try {
      if (isConnected && wsRef.current?.readyState === WebSocket.OPEN) {
        // Send via WebSocket
        wsRef.current.send(JSON.stringify({
          type: 'chat',
          message: inputMessage,
          context: messages.slice(-10) // Send last 10 messages as context
        }));
      } else {
        // Fallback to REST API
        const response = await chatAPI.sendMessage(sessionId, inputMessage, messages.slice(-10));

        const aiMessage = {
          role: 'assistant',
          content: response.message,
          timestamp: response.timestamp,
          id: generateMessageId()
        };

        setMessages(prev => [...prev, aiMessage]);
        setIsLoading(false);
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      setError('Failed to send message. Please try again.');
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <h2>AI Assistant</h2>
        <div className="chat-status">
          <span className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}></span>
          <span>{isConnected ? 'Connected' : 'Reconnecting...'}</span>
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
            ref={inputRef}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
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
        <div className="chat-actions">
          <button onClick={clearChat} className="btn-text">
            Clear Chat
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;