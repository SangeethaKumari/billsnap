import { useState } from "react";
import QueryPanel  from "./components/QueryPanel.jsx";
import ResultPanel from "./components/ResultPanel.jsx";

export default function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleQuery(payload) {
    setLoading(true); 
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/query/", { 
        method: "POST", 
        headers: { "Content-Type": "application/json" }, 
        body: JSON.stringify(payload) 
      });
      if (!res.ok) throw new Error(`Server framework trace error code: ${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch (err) { 
      setError(err.message); 
    } finally { 
      setLoading(false); 
    }
  }

  return (
    <div className="app-shell" style={{ maxWidth: '900px', margin: '2rem auto', padding: '0 1rem', fontFamily: 'system-ui, sans-serif' }}>
      <header className="top-bar" style={{ borderBottom: '2px solid #2d5986', paddingBottom: '1rem', marginBottom: '2rem' }}>
        <h1 style={{ color: '#1a1a2e', margin: 0, fontSize: '2rem' }}>Document Scan Control Center</h1>
        <p style={{ margin: '0.5rem 0 0', color: '#666' }}>Scan billing documents</p>
      </header>
      <main className="workspace">
        <QueryPanel onSubmit={handleQuery} loading={loading} />
        {error && (
          <div className="error-banner" style={{ background: '#fff0f0', border: '1px solid #f5c0c0', padding: '1rem', borderRadius: '4px', color: '#c0392b', margin: '1rem 0' }}>
            <strong>Network Transmission Boundary Exception:</strong> {error}
          </div>
        )}
        {result && <ResultPanel result={result} />}
      </main>
    </div>
  );
}
