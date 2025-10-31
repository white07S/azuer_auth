import React from 'react';

const LoggedOutPage = ({ onLogin }) => (
  <div className="page-container logged-out">
    <header className="page-header">
      <h2>You&apos;re signed out</h2>
      <p className="page-subtitle">
        Access to the workspace requires Azure authentication. Sign in to continue.
      </p>
    </header>

    <div className="page-card">
      <p>
        When you sign in we&apos;ll provision a session, map your Azure AD roles, and
        keep an OpenAI client ready for you.
      </p>
      <button type="button" className="btn-primary btn-full" onClick={onLogin}>
        Sign In with Azure
      </button>
    </div>
  </div>
);

export default LoggedOutPage;
