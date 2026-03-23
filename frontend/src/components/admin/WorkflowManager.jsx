import { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import Loading from '../Loading';
import { getToken } from '../../services/auth';
import { getBaseUrl } from '../../services/api';

function apiRequest(url, options = {}) {
  const baseUrl = getBaseUrl().replace(/\/+$/, '');
  const fullUrl = `${baseUrl}${url}`;
  const token = getToken();
  return fetch(fullUrl, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  }).then(async (r) => {
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    return data;
  });
}

const AGENT_ICONS = {
  Classifier: '🏷️',
  Researcher: '🔍',
  Drafter: '✍️',
  Reviewer: '✅',
};

export default function WorkflowManager() {
  const { isAdmin } = useAuth();
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [ticketId, setTicketId] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [expandedStep, setExpandedStep] = useState(null);
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);

  useEffect(() => {
    if (isAdmin) loadAnalyses();
  }, [isAdmin]);

  const loadAnalyses = async () => {
    setLoading(true);
    try {
      const data = await apiRequest('/workflows/analyses');
      setAnalyses(data.analyses || []);
    } catch (e) {
      alert(`Failed to load analyses: ${e.message}`);
    }
    setLoading(false);
  };

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!ticketId.trim()) return;
    setRunning(true);
    setResult(null);
    setExpandedStep(null);
    try {
      const data = await apiRequest(`/workflows/analyze-ticket/${ticketId}`, {
        method: 'POST',
      });
      setResult(data);
      await loadAnalyses();
    } catch (err) {
      alert(`Analysis failed: ${err.message}`);
    }
    setRunning(false);
  };

  const viewAnalysis = async (id) => {
    try {
      const data = await apiRequest(`/workflows/analyses/${id}`);
      setSelectedAnalysis(data);
      setExpandedStep(null);
    } catch (e) {
      alert(`Failed to load analysis: ${e.message}`);
    }
  };

  const renderSteps = (steps) => (
    <div className="space-y-3">
      {steps.map((step, i) => {
        const isOpen = expandedStep === i;
        const icon = AGENT_ICONS[step.agent_name] || '🤖';
        return (
          <div key={i} className="bg-panel rounded-lg border border-border overflow-hidden">
            <button
              onClick={() => setExpandedStep(isOpen ? null : i)}
              className="w-full flex items-center justify-between p-4 hover:bg-panel-hover transition-all text-left"
            >
              <div className="flex items-center gap-3">
                <span className="text-xl">{icon}</span>
                <div>
                  <span className="text-sm font-medium text-text">{step.agent_name}</span>
                  <span className="text-xs text-muted ml-2">{step.duration_ms}ms</span>
                </div>
              </div>
              <svg
                className={`w-4 h-4 text-muted transition-transform ${isOpen ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {isOpen && (
              <div className="px-4 pb-4 border-t border-border pt-3">
                <pre className="text-xs text-text-secondary bg-bg rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(step.output, null, 2)}
                </pre>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  if (loading) return <Loading />;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text">Multi-Agent Workflows</h1>
        <p className="text-muted text-sm mt-1">
          Run AI analysis pipelines on tickets — Classifier, Researcher, Drafter, and Reviewer agents work together
        </p>
      </div>

      {/* Analyze form */}
      <form onSubmit={handleAnalyze} className="glass rounded-xl p-6 mb-6">
        <label className="block text-sm font-medium text-text mb-2">Ticket ID</label>
        <div className="flex gap-3">
          <input
            type="text"
            value={ticketId}
            onChange={(e) => setTicketId(e.target.value)}
            placeholder="Paste a ticket ID to analyze..."
            required
            className="flex-1 px-4 py-2 bg-panel border border-border rounded-lg text-text placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/50"
          />
          <button
            type="submit"
            disabled={running}
            className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 transition-all text-sm font-medium disabled:opacity-50"
          >
            {running ? 'Running Pipeline...' : 'Analyze Ticket'}
          </button>
        </div>
      </form>

      {running && (
        <div className="glass rounded-xl p-8 text-center mb-6">
          <div className="animate-spin w-8 h-8 border-2 border-accent border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-muted text-sm">
            Running 4-agent pipeline: Classifier → Researcher → Drafter → Reviewer
          </p>
        </div>
      )}

      {/* Current result */}
      {result && (
        <div className="glass rounded-xl p-6 mb-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-text">Analysis Complete</h3>
            <span className={`text-xs px-2 py-1 rounded-full border ${
              result.status === 'completed'
                ? 'bg-green-500/15 text-green-400 border-green-500/30'
                : 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30'
            }`}>
              {result.status}
            </span>
          </div>

          {/* Final output summary */}
          {result.final_output && (
            <div className="bg-panel rounded-lg p-4 border border-accent/30">
              <h4 className="text-sm font-medium text-accent mb-2">Final Output (Reviewer)</h4>
              {result.final_output.revised_response && (
                <p className="text-sm text-text whitespace-pre-wrap">{result.final_output.revised_response}</p>
              )}
              {result.final_output.quality_score !== undefined && (
                <div className="mt-3 flex items-center gap-2">
                  <span className="text-xs text-muted">Quality:</span>
                  <div className="flex-1 bg-bg rounded-full h-2 max-w-xs">
                    <div
                      className="bg-accent rounded-full h-2 transition-all"
                      style={{ width: `${(result.final_output.quality_score * 100).toFixed(0)}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-text">
                    {(result.final_output.quality_score * 100).toFixed(0)}%
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Pipeline steps */}
          <h4 className="text-sm font-medium text-text">Pipeline Steps</h4>
          {renderSteps(result.steps || [])}
        </div>
      )}

      {/* History */}
      <div>
        <h3 className="text-lg font-bold text-text mb-3">Analysis History</h3>
        {analyses.length === 0 ? (
          <div className="glass rounded-xl p-12 text-center">
            <div className="text-4xl mb-3">🔬</div>
            <p className="text-muted">No analyses yet. Enter a ticket ID above to get started.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {analyses.map((a) => (
              <button
                key={a.id}
                onClick={() => viewAnalysis(a.id)}
                className="w-full glass rounded-xl p-4 flex items-center justify-between hover:bg-panel-hover transition-all text-left"
              >
                <div>
                  <div className="text-sm font-medium text-text">
                    Ticket {a.ticket_id?.slice(0, 8)}...
                  </div>
                  <div className="text-xs text-muted mt-1">
                    {a.pipeline_name} — {new Date(a.started_at).toLocaleString()}
                  </div>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full border ${
                  a.status === 'completed'
                    ? 'bg-green-500/15 text-green-400 border-green-500/30'
                    : 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30'
                }`}>
                  {a.status}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Detail modal for history item */}
      {selectedAnalysis && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-bg border border-border rounded-2xl max-w-3xl w-full max-h-[80vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-text">
                Analysis: {selectedAnalysis.ticket_id?.slice(0, 8)}...
              </h3>
              <button
                onClick={() => setSelectedAnalysis(null)}
                className="text-muted hover:text-text transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            {renderSteps(selectedAnalysis.steps || [])}
            {selectedAnalysis.final_output && (
              <div className="bg-panel rounded-lg p-4 border border-accent/30">
                <h4 className="text-sm font-medium text-accent mb-2">Final Output</h4>
                <pre className="text-xs text-text-secondary whitespace-pre-wrap">
                  {JSON.stringify(selectedAnalysis.final_output, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
