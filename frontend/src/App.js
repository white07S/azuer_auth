import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  HashRouter as Router,
  Routes,
  Route,
  useLocation,
  useNavigate,
} from 'react-router-dom';

import Header from './components/Header';
import LoginModal from './components/LoginModal';
import { authAPI } from './api';
import { NAVIGATION_ITEMS, UNAUTHORIZED_ROUTE } from './config/navigation';
import { LoggedOutPage, UnauthorizedPage } from './pages';
import './App.css';

const AppShell = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('sessionId'));
  const [loading, setLoading] = useState(true);
  const refreshIntervalRef = useRef(null);

  const location = useLocation();
  const navigate = useNavigate();

  const stopTokenRefreshMonitor = useCallback(() => {
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }
  }, []);

  const handleLogout = useCallback(async () => {
    try {
      const activeSessionId = localStorage.getItem('sessionId');
      if (activeSessionId) {
        await authAPI.logout(activeSessionId);
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      stopTokenRefreshMonitor();
      localStorage.removeItem('sessionId');
      setSessionId(null);
      setIsAuthenticated(false);
      setSessionInfo(null);
      setShowLoginModal(false);
      navigate('/logged-out', { replace: true });
    }
  }, [navigate, stopTokenRefreshMonitor]);

  const startTokenRefreshMonitor = useCallback(
    (activeSessionId) => {
      if (!activeSessionId) {
        return;
      }

      stopTokenRefreshMonitor();

      refreshIntervalRef.current = setInterval(async () => {
        try {
          const needsRefresh = await authAPI.checkTokenExpiry(activeSessionId);
          if (needsRefresh) {
            await authAPI.refreshToken(activeSessionId);
            console.log('Token refreshed silently');
          }
        } catch (error) {
          console.error('Failed to refresh token:', error);
          await handleLogout();
        }
      }, 30000);
    },
    [handleLogout, stopTokenRefreshMonitor]
  );

  useEffect(() => {
    const initializeSession = async () => {
      try {
        const storedSession = localStorage.getItem('sessionId');
        if (!storedSession) {
          setLoading(false);
          return;
        }

        const info = await authAPI.getSessionInfo(storedSession);
        if (info) {
          setSessionInfo(info);
          setSessionId(storedSession);
          setIsAuthenticated(true);
          startTokenRefreshMonitor(storedSession);
        } else {
          localStorage.removeItem('sessionId');
          setSessionId(null);
        }
      } catch (error) {
        console.error('Failed to check session:', error);
        localStorage.removeItem('sessionId');
        setSessionId(null);
      } finally {
        setLoading(false);
      }
    };

    initializeSession();

    return () => {
      stopTokenRefreshMonitor();
    };
  }, [startTokenRefreshMonitor, stopTokenRefreshMonitor]);

  const handleLoginSuccess = useCallback(async () => {
    setShowLoginModal(false);

    const storedSession = localStorage.getItem('sessionId');
    if (!storedSession) {
      console.warn('Login succeeded but session ID missing');
      return;
    }

    try {
      const info = await authAPI.getSessionInfo(storedSession);
      if (info) {
        setSessionInfo(info);
        setSessionId(storedSession);
        setIsAuthenticated(true);
        startTokenRefreshMonitor(storedSession);
      }
    } catch (error) {
      console.error('Failed to load session after login:', error);
    }
  }, [startTokenRefreshMonitor]);

  const handleLoginError = useCallback((error) => {
    console.error('Login error:', error);
    alert(`Authentication failed: ${error}`);
  }, []);

  useEffect(() => {
    if (
      !loading &&
      !isAuthenticated &&
      !['/', '/logged-out'].includes(location.pathname)
    ) {
      navigate('/logged-out', { replace: true });
    }
  }, [isAuthenticated, loading, location.pathname, navigate]);

  const userRoles = useMemo(() => sessionInfo?.roles || [], [sessionInfo]);

  const availableNavItems = useMemo(() => {
    if (!isAuthenticated) {
      return [];
    }
    return NAVIGATION_ITEMS.filter((item) => {
      if (item.requiresAuth && !isAuthenticated) {
        return false;
      }
      if (!item.roles || item.roles.length === 0) {
        return true;
      }
      return userRoles.some((role) => item.roles.includes(role));
    });
  }, [isAuthenticated, userRoles]);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    if (availableNavItems.length === 0) {
      navigate(UNAUTHORIZED_ROUTE.path, { replace: true });
      return;
    }

    const pathAllowed = availableNavItems.some((item) => item.path === location.pathname);
    if (!pathAllowed) {
      navigate(availableNavItems[0].path, { replace: true });
    }
  }, [availableNavItems, isAuthenticated, location.pathname, navigate]);

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
        navItems={availableNavItems}
      />

      <main className="main-content">
        <Routes>
          {!isAuthenticated && (
            <>
              <Route
                path="/"
                element={<LoggedOutPage onLogin={() => setShowLoginModal(true)} />}
              />
              <Route
                path="/logged-out"
                element={<LoggedOutPage onLogin={() => setShowLoginModal(true)} />}
              />
            </>
          )}

          {isAuthenticated && (
            <>
              {availableNavItems.map((item) => {
                const PageComponent = item.component;
                return (
                  <Route
                    key={item.key}
                    path={item.path}
                    element={
                      <PageComponent
                        userName={sessionInfo?.user_name}
                        roles={userRoles}
                        sessionId={sessionId}
                      />
                    }
                  />
                );
              })}
              <Route path={UNAUTHORIZED_ROUTE.path} element={<UnauthorizedPage />} />
            </>
          )}
        </Routes>
      </main>

      <LoginModal
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
        onLoginSuccess={handleLoginSuccess}
        onError={handleLoginError}
      />
    </div>
  );
};

const App = () => (
  <Router>
    <AppShell />
  </Router>
);

export default App;
