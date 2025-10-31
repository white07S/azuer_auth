import React from 'react';

const mockGlossary = [
  { term: 'Device Code Flow', definition: 'A browserless authentication mechanism for signing in using a secondary device.' },
  { term: 'Session Isolation', definition: 'Each user has a dedicated Azure CLI profile ensuring tokens never overlap.' },
  { term: 'Role Mapping', definition: 'Translating Azure AD group memberships into application privileges.' },
];

const GlossaryPage = ({ userName }) => {
  return (
    <div className="page-container">
      <header className="page-header">
        <h2>Glossary</h2>
        <p className="page-subtitle">
          Key concepts to keep {userName || 'you'} aligned with the platform vocabulary.
        </p>
      </header>

      <dl className="page-glossary">
        {mockGlossary.map((entry) => (
          <div key={entry.term} className="page-card">
            <dt>{entry.term}</dt>
            <dd>{entry.definition}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
};

export default GlossaryPage;
