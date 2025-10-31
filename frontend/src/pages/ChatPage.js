import React from 'react';
import ChatInterface from '../components/ChatInterface';

const ChatPage = ({ sessionId }) => {
  return (
    <div className="page-container">
      <header className="page-header">
        <h2>Chat Assistant</h2>
        <p className="page-subtitle">
          Engage with the Azure OpenAI assistant using your authenticated session credentials.
        </p>
      </header>

      <ChatInterface sessionId={sessionId} />
    </div>
  );
};

export default ChatPage;
