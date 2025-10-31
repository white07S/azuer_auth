import React from 'react';

const mockScenarios = [
  { name: 'Incident Response', detail: 'Generate remediation steps for a Sev2 outage impacting API latency.' },
  { name: 'Onboarding Flow', detail: 'Draft a scripted walkthrough for new support engineers learning Azure AI Chat.' },
];

const ScenarioGeneratorPage = ({ userName }) => {
  return (
    <div className="page-container">
      <header className="page-header">
        <h2>Scenario Generator</h2>
        <p className="page-subtitle">
          Build guided conversations tailored to {userName || 'your team'} with reusable prompts.
        </p>
      </header>

      <div className="page-list">
        {mockScenarios.map((scenario) => (
          <article key={scenario.name} className="page-card">
            <h3>{scenario.name}</h3>
            <p>{scenario.detail}</p>
            <button type="button" className="btn-primary btn-small">Generate Draft</button>
          </article>
        ))}
      </div>
    </div>
  );
};

export default ScenarioGeneratorPage;
