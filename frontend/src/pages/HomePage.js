import React from 'react';

const mockHighlights = [
  { title: 'Latest Model Update', description: 'GPT-4.2 Turbo now available with extended context windows.' },
  { title: 'Usage Snapshot', description: 'You have exchanged 18 messages with the assistant today.' },
  { title: 'Tip of the Day', description: 'Remember to tag scenarios with business impact for quick retrieval.' },
];

const HomePage = ({ userName }) => {
  return (
    <div className="page-container">
      <header className="page-header">
        <h2>Welcome back, {userName || 'there'}!</h2>
        <p className="page-subtitle">
          Here&apos;s a quick snapshot of what&apos;s happening across your AI workspace today.
        </p>
      </header>

      <div className="page-grid">
        {mockHighlights.map((item) => (
          <article key={item.title} className="page-card">
            <h3>{item.title}</h3>
            <p>{item.description}</p>
          </article>
        ))}
      </div>
    </div>
  );
};

export default HomePage;
