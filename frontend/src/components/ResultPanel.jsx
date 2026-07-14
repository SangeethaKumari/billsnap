export default function ResultPanel({ result }) {
  return (
    <section className="result-panel" style={{ background: '#fff', padding: '1.5rem', border: '1px solid #d8d2c8', borderRadius: '4px' }}>
      <h2 style={{ color: '#2d5986', marginTop: 0, borderBottom: '1px solid #eee', paddingBottom: '0.5rem', fontSize: '1.25rem' }}>Dynamic Engine Response Context</h2>
      <p style={{ lineHeight: '1.6', fontSize: '1.05rem', color: '#1a1a2e', whiteSpace: 'pre-wrap' }}>{result.answer}</p>
      
      {result.citations?.length > 0 && (
        <div style={{ marginTop: '1rem' }}>
          <h4 style={{ margin: '0 0 0.25rem 0', color: '#444' }}>Grounded Target Citation Vectors</h4>
          <ul style={{ paddingLeft: '1.25rem', margin: 0, fontSize: '0.9rem' }}>
            {result.citations.map((c, i) => (
              <li key={i} style={{ marginBottom: '0.25rem' }}>
                <span style={{ fontFamily: 'monospace', background: '#eee', padding: '2px 4px' }}>Source Node</span> — {c.title} {c.uri && <a href={c.uri} target="_blank" rel="noreferrer">[{c.uri}]</a>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div style={{ marginTop: '1.5rem', background: '#eef2f7', padding: '1rem', borderRadius: '4px' }}>
        <h4 style={{ margin: '0 0 0.5rem 0', color: '#555', textTransform: 'uppercase', fontSize: '0.8rem' }}>Arize Phoenix Telemetry Spans Trace Logs</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', fontSize: '0.85rem' }}>
          <div><strong>Metric Graph Trace Propagation Index:</strong> {(result.confidence * 100).toFixed(0)}%</div>
          <div><strong>OTel Step Chain Topology:</strong> {result.constraint_chain?.join(" ➔ ") || "Direct Evaluation"}</div>
        </div>
      </div>
    </section>
  );
}
