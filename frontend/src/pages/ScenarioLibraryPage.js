import React from 'react';

const mockScenarioLibrary = [
  { name: 'Quarterly Business Review', tags: ['executive', 'summary'], lastUpdated: '2 days ago' },
  { name: 'Support Escalation', tags: ['operations', 'handoff'], lastUpdated: '5 days ago' },
  { name: 'Compliance Checklist', tags: ['legal', 'review'], lastUpdated: '1 week ago' },
];

const ScenarioLibraryPage = ({ userName }) => {
  return (
    <div className="page-container">
      <header className="page-header">
        <h2>Scenario Library</h2>
        <p className="page-subtitle">
          Browse curated scenarios contributed by {userName || 'your peers'} and reuse them for upcoming engagements.
        </p>
      </header>

      <div className="page-list">
        {mockScenarioLibrary.map((scenario) => (
          <article key={scenario.name} className="page-card">
            <h3>{scenario.name}</h3>
            <p>Tags: {scenario.tags.join(', ')}</p>
            <small>Last updated {scenario.lastUpdated}</small>
          </article>
        ))}
      </div>
    </div>
  );
};

export default ScenarioLibraryPage;
