import React from 'react';

const mockMetrics = [
  { label: 'Active Sessions', value: 6, trend: '+2 this week' },
  { label: 'Token Refreshes', value: 14, trend: 'auto refreshed seamlessly' },
  { label: 'Average Response Time', value: '1.8s', trend: 'steady performance' },
];

const DashboardPage = ({ userName }) => {
  return (
    <div className="page-container">
      <header className="page-header">
        <h2>Operations Dashboard</h2>
        <p className="page-subtitle">
          Monitor health metrics and usage patterns across Azure AI sessions for {userName || 'your organization'}.
        </p>
      </header>

      <div className="page-grid">
        {mockMetrics.map((metric) => (
          <article key={metric.label} className="page-card">
            <h3>{metric.value}</h3>
            <p>{metric.label}</p>
            <small>{metric.trend}</small>
          </article>
        ))}
      </div>
    </div>
  );
};

export default DashboardPage;
