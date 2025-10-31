import React, { useState, useEffect } from 'react';
import LoginModal from './components/LoginModal';
import ChatInterface from './components/ChatInterface';
import Header from './components/Header';
import { authAPI } from './utils/api';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkSession();
  }, []);

  const checkSession = async () => {
    try {
      // Check if there's a stored session
      const storedSession = localStorage.getItem('sessionId');
      if (storedSession) {
        const info = await authAPI.getSessionInfo(storedSession);
        if (info) {
          setSessionInfo(info);
          setIsAuthenticated(true);

          // Start token refresh monitoring
          startTokenRefreshMonitor(storedSession);
        } else {
          localStorage.removeItem('sessionId');
        }
      }
    } catch (error) {
      console.error('Failed to check session:', error);
      localStorage.removeItem('sessionId');
    } finally {
      setLoading(false);
    }
  };

  const startTokenRefreshMonitor = (sessionId) => {
    // Check token status every 30 seconds
    const interval = setInterval(async () => {
      try {
        const needsRefresh = await authAPI.checkTokenExpiry(sessionId);
        if (needsRefresh) {
          await authAPI.refreshToken(sessionId);
          console.log('Token refreshed silently');
        }
      } catch (error) {
        console.error('Failed to refresh token:', error);
        // If refresh fails, logout
        handleLogout();
      }
    }, 30000); // 30 seconds

    // Store interval ID for cleanup
    window.tokenRefreshInterval = interval;
  };

  const handleLoginSuccess = async () => {
    setIsAuthenticated(true);
    setShowLoginModal(false);

    // Get session info
    const storedSession = localStorage.getItem('sessionId');
    if (storedSession) {
      const info = await authAPI.getSessionInfo(storedSession);
      setSessionInfo(info);

      // Start token refresh monitoring
      startTokenRefreshMonitor(storedSession);
    }
  };

  const handleLoginError = (error) => {
    console.error('Login error:', error);
    alert(`Authentication failed: ${error}`);
  };

  const handleLogout = async () => {
    try {
      const sessionId = localStorage.getItem('sessionId');
      if (sessionId) {
        await authAPI.logout(sessionId);
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear local state
      localStorage.removeItem('sessionId');
      setIsAuthenticated(false);
      setSessionInfo(null);

      // Clear refresh interval
      if (window.tokenRefreshInterval) {
        clearInterval(window.tokenRefreshInterval);
      }
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div className="app">
      <Header
        isAuthenticated={isAuthenticated}
        userInfo={sessionInfo}
        onLogin={() => setShowLoginModal(true)}
        onLogout={handleLogout}
      />

      <main className="main-content">
        {isAuthenticated ? (
          <ChatInterface sessionId={localStorage.getItem('sessionId')} />
        ) : (
          <div className="welcome-container">
            <h1>Welcome to Azure AI Chat</h1>
            <p>Please sign in with your Azure account to start chatting.</p>
            <button
              className="btn-primary"
              onClick={() => setShowLoginModal(true)}
            >
              Sign In with Azure
            </button>
          </div>
        )}
      </main>

      <LoginModal
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
        onLoginSuccess={handleLoginSuccess}
        onError={handleLoginError}
      />
    </div>
  );
}

export default App;
