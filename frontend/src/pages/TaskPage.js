import React from 'react';

const mockTasks = [
  { title: 'Review access policies', due: 'Today', assignee: 'Security Team' },
  { title: 'Publish scenario templates', due: 'Tomorrow', assignee: 'Experience Lab' },
  { title: 'Update onboarding doc', due: 'Friday', assignee: 'Ops Enablement' },
];

const TaskPage = ({ userName }) => {
  return (
    <div className="page-container">
      <header className="page-header">
        <h2>Task Board</h2>
        <p className="page-subtitle">
          Track follow-ups assigned to {userName || 'your team'} to keep AI initiatives on schedule.
        </p>
      </header>

      <div className="page-list">
        {mockTasks.map((task) => (
          <article key={task.title} className="page-card">
            <h3>{task.title}</h3>
            <p>Due: {task.due}</p>
            <small>Owner: {task.assignee}</small>
          </article>
        ))}
      </div>
    </div>
  );
};

export default TaskPage;
