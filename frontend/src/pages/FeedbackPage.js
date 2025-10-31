import React, { useState } from 'react';

const FeedbackPage = ({ userName }) => {
  const [feedback, setFeedback] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (event) => {
    event.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="page-container">
      <header className="page-header">
        <h2>Feedback</h2>
        <p className="page-subtitle">
          Share insights or blockers so the platform keeps working for {userName || 'you'}.
        </p>
      </header>

      <form className="page-card page-form" onSubmit={handleSubmit}>
        <label htmlFor="feedback" className="page-form-label">How can we improve?</label>
        <textarea
          id="feedback"
          className="page-form-textarea"
          value={feedback}
          onChange={(event) => setFeedback(event.target.value)}
          placeholder="Tell us what worked well or what needs attention..."
          rows={5}
          required
        />
        <button type="submit" className="btn-primary btn-full">
          Submit Feedback
        </button>
        {submitted && (
          <p className="page-subtitle success-message">
            Thank you! Your note has been captured for the product team.
          </p>
        )}
      </form>
    </div>
  );
};

export default FeedbackPage;
