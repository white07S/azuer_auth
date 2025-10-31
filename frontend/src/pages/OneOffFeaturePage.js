import React from 'react';

const mockIdeas = [
  { name: 'Transcript Export', status: 'Prototype ready', owner: 'Grace' },
  { name: 'Real-time Sentiment Overlay', status: 'Exploration', owner: 'Alex' },
];

const OneOffFeaturePage = ({ userName }) => {
  return (
    <div className="page-container">
      <header className="page-header">
        <h2>One-off Feature Experiments</h2>
        <p className="page-subtitle">
          Evaluate in-flight experiments curated by {userName || 'your innovation group'}.
        </p>
      </header>

      <div className="page-list">
        {mockIdeas.map((idea) => (
          <article key={idea.name} className="page-card">
            <h3>{idea.name}</h3>
            <p>Status: {idea.status}</p>
            <small>Owner: {idea.owner}</small>
          </article>
        ))}
      </div>
    </div>
  );
};

export default OneOffFeaturePage;
