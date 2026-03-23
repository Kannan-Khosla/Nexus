import { useState, useEffect, useRef } from 'react';
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
      ...(options.headers || {}),
      ...(token && { Authorization: `Bearer ${token}` }),
      ...(!options.isFormData && { 'Content-Type': 'application/json' }),
    },
  }).then(async (r) => {
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    return data;
  });
}

export default function KnowledgeBase() {
  const { isAdmin } = useAuth();
  const [tab, setTab] = useState('documents');
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);

  // Chat state
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  const fileInputRef = useRef(null);

  useEffect(() => {
    if (isAdmin) loadDocuments();
  }, [isAdmin]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const data = await apiRequest('/knowledge/documents');
      setDocuments(data.documents || []);
    } catch (e) {
      alert(`Failed to load documents: ${e.message}`);
    }
    setLoading(false);
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name.replace(/\.[^.]+$/, ''));
    formData.append('source', 'manual');

    const baseUrl = getBaseUrl().replace(/\/+$/, '');
    const token = getToken();
    try {
      const resp = await fetch(`${baseUrl}/knowledge/documents`, {
        method: 'POST',
        headers: { ...(token && { Authorization: `Bearer ${token}` }) },
        body: formData,
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
      await loadDocuments();
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this document and all its chunks?')) return;
    try {
      await apiRequest(`/knowledge/documents/${id}`, { method: 'DELETE' });
      await loadDocuments();
    } catch (e) {
      alert(`Delete failed: ${e.message}`);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const data = await apiRequest('/knowledge/search', {
        method: 'POST',
        body: JSON.stringify({ query: searchQuery, top_k: 5 }),
      });
      setSearchResults(data.results || []);
    } catch (e) {
      alert(`Search failed: ${e.message}`);
    }
    setSearching(false);
  };

  const handleChat = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    const question = chatInput;
    setChatInput('');
    setChatHistory((h) => [...h, { role: 'user', content: question }]);
    setChatLoading(true);
    try {
      const data = await apiRequest('/knowledge/chat', {
        method: 'POST',
        body: JSON.stringify({ question, top_k: 5 }),
      });
      setChatHistory((h) => [
        ...h,
        { role: 'assistant', content: data.answer, sources: data.sources },
      ]);
    } catch (err) {
      setChatHistory((h) => [
        ...h,
        { role: 'assistant', content: `Error: ${err.message}` },
      ]);
    }
    setChatLoading(false);
  };

  if (loading) return <Loading />;

  const tabs = [
    { id: 'documents', label: 'Documents' },
    { id: 'search', label: 'Search' },
    { id: 'chat', label: 'AI Chat' },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text">Knowledge Base</h1>
          <p className="text-muted text-sm mt-1">Upload documents, search semantically, and chat with your knowledge base</p>
        </div>
      </div>

      {/* Tabs */}
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

      {/* Documents Tab */}
      {tab === 'documents' && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt,.md,.csv"
              onChange={handleUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 transition-all text-sm font-medium disabled:opacity-50"
            >
              {uploading ? 'Uploading...' : 'Upload Document'}
            </button>
          </div>

          {documents.length === 0 ? (
            <div className="glass rounded-xl p-12 text-center">
              <div className="text-4xl mb-3">📄</div>
              <p className="text-muted">No documents yet. Upload a PDF, DOCX, or TXT file to get started.</p>
            </div>
          ) : (
            <div className="grid gap-3">
              {documents.map((doc) => (
                <div key={doc.id} className="glass rounded-xl p-4 flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-text">{doc.title}</h3>
                    <div className="flex gap-4 mt-1 text-xs text-muted">
                      <span>{doc.total_chunks} chunks</span>
                      <span>{doc.source}</span>
                      <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="px-3 py-1.5 bg-red-500/10 text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/20 transition-all text-sm"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Search Tab */}
      {tab === 'search' && (
        <div className="space-y-4">
          <form onSubmit={handleSearch} className="flex gap-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search your knowledge base..."
              className="flex-1 px-4 py-2 bg-panel border border-border rounded-lg text-text placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/50"
            />
            <button
              type="submit"
              disabled={searching}
              className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 transition-all text-sm font-medium disabled:opacity-50"
            >
              {searching ? 'Searching...' : 'Search'}
            </button>
          </form>

          {searchResults.length > 0 && (
            <div className="space-y-3">
              {searchResults.map((r, i) => (
                <div key={i} className="glass rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-accent">{r.document_title || 'Unknown'}</span>
                    <span className="text-xs text-muted bg-panel px-2 py-1 rounded-full">
                      {(r.similarity * 100).toFixed(1)}% match
                    </span>
                  </div>
                  <p className="text-sm text-text-secondary whitespace-pre-wrap">{r.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Chat Tab */}
      {tab === 'chat' && (
        <div className="glass rounded-xl flex flex-col" style={{ height: '60vh' }}>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {chatHistory.length === 0 && (
              <div className="text-center text-muted py-12">
                <div className="text-4xl mb-3">🤖</div>
                <p>Ask a question about your knowledge base</p>
              </div>
            )}
            {chatHistory.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] rounded-xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-accent text-white'
                      : 'bg-panel border border-border text-text'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  {msg.sources?.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-border/50">
                      <p className="text-xs opacity-70 mb-1">Sources:</p>
                      {msg.sources.map((s, j) => (
                        <span key={j} className="inline-block text-xs bg-bg/30 rounded px-2 py-0.5 mr-1 mb-1">
                          {s.document_title} ({(s.similarity * 100).toFixed(0)}%)
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-panel border border-border rounded-xl px-4 py-3">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-accent rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                    <div className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <form onSubmit={handleChat} className="p-4 border-t border-border flex gap-3">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask a question..."
              className="flex-1 px-4 py-2 bg-panel border border-border rounded-lg text-text placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/50"
            />
            <button
              type="submit"
              disabled={chatLoading || !chatInput.trim()}
              className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 transition-all text-sm font-medium disabled:opacity-50"
            >
              Send
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
