import React from 'react';
import { User, Bot } from 'lucide-react';

const MessageList = ({ messages, isLoading }) => {
  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  };

  const formatMessage = (content) => {
    // Basic markdown formatting
    // Convert bold text
    content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Convert italic text
    content = content.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Convert code blocks
    content = content.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');

    // Convert inline code
    content = content.replace(/`(.*?)`/g, '<code>$1</code>');

    // Convert line breaks
    content = content.replace(/\n/g, '<br/>');

    return content;
  };

  return (
    <div className="message-list">
      {messages.length === 0 ? (
        <div className="empty-chat">
          <Bot size={48} className="empty-icon" />
          <h3>Start a conversation</h3>
          <p>Type a message below to begin chatting with your AI assistant.</p>
        </div>
      ) : (
        messages.map((message) => (
          <div
            key={message.id || `${message.role}_${message.timestamp}`}
            className={`message ${message.role}`}
          >
            <div className="message-avatar">
              {message.role === 'user' ? (
                <User size={20} />
              ) : (
                <Bot size={20} />
              )}
            </div>
            <div className="message-content">
              <div className="message-header">
                <span className="message-role">
                  {message.role === 'user' ? 'You' : 'AI Assistant'}
                </span>
                <span className="message-time">
                  {formatTime(message.timestamp)}
                </span>
              </div>
              <div
                className="message-text"
                dangerouslySetInnerHTML={{ __html: formatMessage(message.content) }}
              />
            </div>
          </div>
        ))
      )}

      {isLoading && (
        <div className="message assistant loading-message">
          <div className="message-avatar">
            <Bot size={20} />
          </div>
          <div className="message-content">
            <div className="message-header">
              <span className="message-role">AI Assistant</span>
            </div>
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MessageList;