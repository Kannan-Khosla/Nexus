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

const STATUS_COLORS = {
  pass: 'bg-green-500/15 text-green-400 border-green-500/30',
  fail: 'bg-red-500/15 text-red-400 border-red-500/30',
  partial: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  not_applicable: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
};

export default function ComplianceManager() {
  const { isAdmin } = useAuth();
  const [tab, setTab] = useState('templates');
  const [templates, setTemplates] = useState([]);
  const [evaluations, setEvaluations] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

  // Create template
  const [showCreate, setShowCreate] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [templateDesc, setTemplateDesc] = useState('');
  const [requirements, setRequirements] = useState([{ id: 'req-1', title: '', description: '', category: '' }]);

  // Evaluate
  const [evalDocId, setEvalDocId] = useState('');
  const [evalTmplId, setEvalTmplId] = useState('');
  const [evaluating, setEvaluating] = useState(false);
  const [evalResult, setEvalResult] = useState(null);

  useEffect(() => {
    if (isAdmin) loadAll();
  }, [isAdmin]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [tmpl, evals, docs] = await Promise.all([
        apiRequest('/compliance/templates'),
        apiRequest('/compliance/evaluations'),
        apiRequest('/knowledge/documents'),
      ]);
      setTemplates(tmpl.templates || []);
      setEvaluations(evals.evaluations || []);
      setDocuments(docs.documents || []);
    } catch (e) {
      alert(`Failed to load: ${e.message}`);
    }
    setLoading(false);
  };

  const addRequirement = () => {
    setRequirements((prev) => [
      ...prev,
      { id: `req-${prev.length + 1}`, title: '', description: '', category: '' },
    ]);
  };

  const updateReq = (index, field, value) => {
    setRequirements((prev) => prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)));
  };

  const removeReq = (index) => {
    setRequirements((prev) => prev.filter((_, i) => i !== index));
  };

  const handleCreateTemplate = async (e) => {
    e.preventDefault();
    try {
      await apiRequest('/compliance/templates', {
        method: 'POST',
        body: JSON.stringify({
          name: templateName,
          description: templateDesc,
          requirements: requirements.filter((r) => r.title.trim()),
        }),
      });
      setShowCreate(false);
      setTemplateName('');
      setTemplateDesc('');
      setRequirements([{ id: 'req-1', title: '', description: '', category: '' }]);
      await loadAll();
    } catch (e) {
      alert(`Failed to create template: ${e.message}`);
    }
  };

  const handleEvaluate = async (e) => {
    e.preventDefault();
    if (!evalDocId || !evalTmplId) return;
    setEvaluating(true);
    setEvalResult(null);
    try {
      const data = await apiRequest('/compliance/evaluate', {
        method: 'POST',
        body: JSON.stringify({ document_id: evalDocId, template_id: evalTmplId }),
      });
      setEvalResult(data);
      await loadAll();
    } catch (err) {
      alert(`Evaluation failed: ${err.message}`);
    }
    setEvaluating(false);
  };

  if (loading) return <Loading />;

  const tabs = [
    { id: 'templates', label: 'Templates' },
    { id: 'evaluate', label: 'Evaluate' },
    { id: 'history', label: 'History' },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text">Compliance Evaluation</h1>
        <p className="text-muted text-sm mt-1">Define requirement templates and evaluate documents against them</p>
      </div>

      <div className="flex gap-2 mb-6">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t.id
                ? 'bg-accent/20 text-accent border border-accent/30'
                : 'text-text-secondary hover:text-text hover:bg-panel-hover border border-transparent'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Templates Tab */}
      {tab === 'templates' && (
        <div className="space-y-4">
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 transition-all text-sm font-medium"
          >
            {showCreate ? 'Cancel' : 'Create Template'}
          </button>

          {showCreate && (
            <form onSubmit={handleCreateTemplate} className="glass rounded-xl p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-text mb-1">Template Name</label>
                <input
                  type="text"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  required
                  className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
                  placeholder="e.g. SOC 2 Type II"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text mb-1">Description</label>
                <input
                  type="text"
                  value={templateDesc}
                  onChange={(e) => setTemplateDesc(e.target.value)}
                  className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
                  placeholder="Optional description"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-text">Requirements</label>
                  <button
                    type="button"
                    onClick={addRequirement}
                    className="text-xs text-accent hover:underline"
                  >
                    + Add Requirement
                  </button>
                </div>
                <div className="space-y-3">
                  {requirements.map((req, i) => (
                    <div key={i} className="bg-panel rounded-lg p-3 border border-border space-y-2">
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={req.title}
                          onChange={(e) => updateReq(i, 'title', e.target.value)}
                          placeholder="Requirement title"
                          className="flex-1 px-3 py-1.5 bg-bg border border-border rounded text-sm text-text focus:outline-none"
                        />
                        <input
                          type="text"
                          value={req.category}
                          onChange={(e) => updateReq(i, 'category', e.target.value)}
                          placeholder="Category"
                          className="w-32 px-3 py-1.5 bg-bg border border-border rounded text-sm text-text focus:outline-none"
                        />
                        {requirements.length > 1 && (
                          <button type="button" onClick={() => removeReq(i)} className="text-red-400 text-sm px-2">
                            x
                          </button>
                        )}
                      </div>
                      <textarea
                        value={req.description}
                        onChange={(e) => updateReq(i, 'description', e.target.value)}
                        placeholder="Describe what compliance with this requirement looks like"
                        rows={2}
                        className="w-full px-3 py-1.5 bg-bg border border-border rounded text-sm text-text focus:outline-none resize-none"
                      />
                    </div>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 transition-all text-sm font-medium"
              >
                Save Template
              </button>
            </form>
          )}

          {templates.length === 0 && !showCreate ? (
            <div className="glass rounded-xl p-12 text-center">
              <div className="text-4xl mb-3">📋</div>
              <p className="text-muted">No templates yet. Create one to start evaluating documents.</p>
            </div>
          ) : (
            <div className="grid gap-3">
              {templates.map((t) => (
                <div key={t.id} className="glass rounded-xl p-4">
                  <h3 className="font-medium text-text">{t.name}</h3>
                  {t.description && <p className="text-sm text-muted mt-1">{t.description}</p>}
                  <div className="text-xs text-muted mt-2">
                    {(t.requirements || []).length} requirement(s)
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Evaluate Tab */}
      {tab === 'evaluate' && (
        <div className="space-y-4">
          <form onSubmit={handleEvaluate} className="glass rounded-xl p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-text mb-1">Document</label>
              <select
                value={evalDocId}
                onChange={(e) => setEvalDocId(e.target.value)}
                required
                className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
              >
                <option value="">Select a document...</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>{d.title}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-text mb-1">Template</label>
              <select
                value={evalTmplId}
                onChange={(e) => setEvalTmplId(e.target.value)}
                required
                className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
              >
                <option value="">Select a template...</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              disabled={evaluating}
              className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 transition-all text-sm font-medium disabled:opacity-50"
            >
              {evaluating ? 'Evaluating...' : 'Run Evaluation'}
            </button>
          </form>

          {evaluating && (
            <div className="glass rounded-xl p-8 text-center">
              <div className="animate-spin w-8 h-8 border-2 border-accent border-t-transparent rounded-full mx-auto mb-3" />
              <p className="text-muted text-sm">AI is evaluating each requirement... this may take a moment.</p>
            </div>
          )}

          {evalResult && (
            <div className="glass rounded-xl p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-text">Evaluation Result</h3>
                <div className="flex items-center gap-2">
                  <div className={`text-2xl font-bold ${evalResult.overall_score >= 0.7 ? 'text-green-400' : evalResult.overall_score >= 0.4 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {(evalResult.overall_score * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
              <p className="text-sm text-muted">{evalResult.summary}</p>

              <div className="space-y-3">
                {evalResult.results?.map((r, i) => (
                  <div key={i} className="bg-panel rounded-lg p-4 border border-border">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-text">{r.requirement_id}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full border ${STATUS_COLORS[r.status] || ''}`}>
                        {r.status.replace('_', ' ')}
                      </span>
                    </div>
                    <p className="text-sm text-text-secondary">{r.reasoning}</p>
                    {r.evidence && (
                      <p className="text-xs text-muted mt-2 italic border-l-2 border-accent/30 pl-2">
                        "{r.evidence}"
                      </p>
                    )}
                    <div className="mt-2">
                      <div className="w-full bg-bg rounded-full h-1.5">
                        <div
                          className="bg-accent rounded-full h-1.5 transition-all"
                          style={{ width: `${(r.confidence * 100).toFixed(0)}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted">{(r.confidence * 100).toFixed(0)}% confidence</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* History Tab */}
      {tab === 'history' && (
        <div className="space-y-3">
          {evaluations.length === 0 ? (
            <div className="glass rounded-xl p-12 text-center">
              <div className="text-4xl mb-3">📊</div>
              <p className="text-muted">No evaluations yet. Run one from the Evaluate tab.</p>
            </div>
          ) : (
            evaluations.map((ev) => (
              <div key={ev.id} className="glass rounded-xl p-4 flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium text-text">
                    Evaluation {ev.id.slice(0, 8)}...
                  </div>
                  <p className="text-xs text-muted mt-1">{ev.summary}</p>
                  <span className="text-xs text-muted">{new Date(ev.evaluated_at).toLocaleString()}</span>
                </div>
                <div className={`text-lg font-bold ${(ev.overall_score || 0) >= 0.7 ? 'text-green-400' : (ev.overall_score || 0) >= 0.4 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {((ev.overall_score || 0) * 100).toFixed(0)}%
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
