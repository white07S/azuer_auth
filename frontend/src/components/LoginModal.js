import React, { useState, useEffect } from 'react';
import { X, Copy, CheckCircle } from 'lucide-react';
import { authAPI } from '../utils/api';

const LoginModal = ({ isOpen, onClose, onLoginSuccess, onError }) => {
  const [step, setStep] = useState('idle'); // idle, loading, code, polling, success, error
  const [userCode, setUserCode] = useState('');
  const [verificationUri, setVerificationUri] = useState('');
  const [copied, setCopied] = useState(false);
  const [sessionId, setSessionId] = useState(null);

  useEffect(() => {
    if (!isOpen) {
      // Reset state when modal closes
      setStep('idle');
      setUserCode('');
      setVerificationUri('');
      setCopied(false);
      setSessionId(null);
    }
  }, [isOpen]);

  const startLogin = async () => {
    setStep('loading');
    try {
      const data = await authAPI.startAuth();
      setUserCode(data.user_code);
      setVerificationUri(data.verification_uri);
      setSessionId(data.session_id);
      setStep('code');

      // Store session ID in localStorage
      localStorage.setItem('sessionId', data.session_id);

      // Start polling for auth status
      pollAuthStatus(data.session_id);
    } catch (error) {
      setStep('error');
      onError(error.response?.data?.detail || 'Failed to start authentication');
    }
  };

  const pollAuthStatus = async (sid) => {
    setStep('polling');
    const maxAttempts = 150; // Poll for 5 minutes (2 second intervals)
    let attempts = 0;

    const poll = async () => {
      if (attempts >= maxAttempts) {
        setStep('error');
        onError('Authentication timeout. Please try again.');
        return;
      }

      try {
        const status = await authAPI.checkAuthStatus(sid);

        if (status.status === 'completed') {
          if (status.authorized) {
            // Complete the auth flow
            try {
              await authAPI.completeAuth(sid);
              setStep('success');
              // Trigger success callback immediately, then close
              onLoginSuccess();
              setTimeout(() => {
                onClose();
              }, 800);
              return; // Stop polling
            } catch (error) {
              setStep('error');
              onError(error.response?.data?.detail || 'Failed to complete authentication');
              return;
            }
          } else {
            setStep('error');
            onError('User not authorized. Please contact administrator.');
          }
        } else if (status.status === 'error' || status.status === 'timeout') {
          setStep('error');
          onError(status.message || 'Authentication failed');
        } else {
          // Continue polling
          attempts++;
          setTimeout(poll, 2000);
        }
      } catch (error) {
        setStep('error');
        onError(error.response?.data?.detail || 'Authentication failed');
      }
    };

    poll();
  };

  const copyCode = () => {
    navigator.clipboard.writeText(userCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const openVerificationUrl = () => {
    window.open(verificationUri, '_blank');
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-container">
        {/* Header */}
        <div className="modal-header">
          <h2>Sign In</h2>
          <button
            onClick={onClose}
            className="btn-icon"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="modal-body">
          {step === 'idle' && (
            <div className="auth-step">
              <p className="auth-description">
                Sign in with your Azure account to access protected resources.
              </p>
              <button
                onClick={startLogin}
                className="btn-primary btn-full"
              >
                Sign in with Azure
              </button>
            </div>
          )}

          {step === 'loading' && (
            <div className="auth-step auth-loading">
              <div className="spinner"></div>
              <p>Initializing authentication...</p>
            </div>
          )}

          {(step === 'code' || step === 'polling') && (
            <div className="auth-step">
              <p className="auth-description">
                To complete sign in, use a web browser to open the page below and enter the following code:
              </p>

              <div className="code-container">
                <div className="user-code">
                  {userCode}
                </div>
                <button
                  onClick={copyCode}
                  className="btn-icon btn-copy"
                  title="Copy code"
                >
                  {copied ? <CheckCircle size={20} className="icon-success" /> : <Copy size={20} />}
                </button>
              </div>

              <button
                onClick={openVerificationUrl}
                className="btn-primary btn-full"
              >
                Open Authentication Page
              </button>

              {step === 'polling' && (
                <div className="polling-status">
                  <div className="spinner-small"></div>
                  <span>Waiting for authentication...</span>
                </div>
              )}

              <div className="auth-url">
                <small>Or manually navigate to: {verificationUri}</small>
              </div>
            </div>
          )}

          {step === 'success' && (
            <div className="auth-step auth-success">
              <CheckCircle size={48} className="icon-success-large" />
              <p>Authentication successful!</p>
            </div>
          )}

          {step === 'error' && (
            <div className="auth-step">
              <p className="error-message">Authentication failed</p>
              <button
                onClick={() => {
                  setStep('idle');
                  setUserCode('');
                  setVerificationUri('');
                  setSessionId(null);
                }}
                className="btn-primary btn-full"
              >
                Try Again
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LoginModal;