import { useState } from "react";

export default function QueryPanel({ onSubmit, loading }) {
  const [question, setQuestion] = useState("");
  const [context, setContext] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (!question.trim()) return;
    onSubmit({ question, context: context ? { target_scope: context } : {} });
  }

  return (
    <section className="query-panel" style={{ background: '#fff', padding: '1.5rem', border: '1px solid #d8d2c8', borderRadius: '4px', marginBottom: '1.5rem' }}>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="question" style={{ display: 'block', fontWeight: '600', marginBottom: '0.5rem', fontSize: '0.9rem' }}>Agent System Instruction Query Prompt</label>
          <textarea id="question" rows={4} style={{ width: '100%', padding: '0.75rem', border: '1px solid #ccc', borderRadius: '4px', fontSize: '1rem', fontFamily: 'inherit' }} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Submit analytical target specifications..." disabled={loading} />
        </div>
        <div style={{ marginBottom: '1.5rem' }}>
          <label htmlFor="context" style={{ display: 'block', fontWeight: '600', marginBottom: '0.5rem', fontSize: '0.9rem' }}>Scope Parameter Context Filtering Flags (Optional)</label>
          <input id="context" type="text" style={{ width: '100%', padding: '0.75rem', border: '1px solid #ccc', borderRadius: '4px', fontSize: '1rem' }} value={context} onChange={(e) => setContext(e.target.value)} placeholder="Context scope rules mapping descriptor..." disabled={loading} />
        </div>
        <button type="submit" style={{ padding: '0.75rem 1.5rem', background: '#2d5986', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '1rem', fontWeight: '600' }} disabled={loading || !question.trim()}>
          {loading ? "Streaming Agent Session Graph Execution..." : "Fire Query Request →"}
        </button>
      </form>
    </section>
  );
}
