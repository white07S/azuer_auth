import React from 'react';

const UnauthorizedPage = () => (
  <div className="page-container">
    <header className="page-header">
      <h2>Access Restricted</h2>
      <p className="page-subtitle">
        You don&apos;t have the necessary role to view this area. Please contact an administrator if you believe this is an error.
      </p>
    </header>
  </div>
);

export default UnauthorizedPage;
