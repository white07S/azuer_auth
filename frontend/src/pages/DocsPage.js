import React from 'react';

const mockDocs = [
  { title: 'Getting Started', description: 'Connect to Azure OpenAI and authenticate users with device code flow.' },
  { title: 'Prompt Guidelines', description: 'Best practices for creating consistent prompts with guardrails.' },
  { title: 'API Reference', description: 'Endpoints available in the Auth Azure backend and how to extend them.' },
];

const DocsPage = ({ userName }) => {
  return (
    <div className="page-container">
      <header className="page-header">
        <h2>Documentation</h2>
        <p className="page-subtitle">
          Curated guides to help {userName || 'you'} build, deploy, and maintain conversation experiences.
        </p>
      </header>

      <div className="page-list">
        {mockDocs.map((doc) => (
          <article key={doc.title} className="page-card">
            <h3>{doc.title}</h3>
            <p>{doc.description}</p>
            <button type="button" className="btn-text link-button">View Guide</button>
          </article>
        ))}
      </div>
    </div>
  );
};

export default DocsPage;
