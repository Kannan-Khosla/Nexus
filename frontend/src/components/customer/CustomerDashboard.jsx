import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { getCustomerTickets, createTicket } from '../../services/api';
import Loading from '../Loading';

function Badge({ status }) {
  const className = {
    open: 'bg-green-500/20 text-green-400 border-green-500/50',
    human_assigned: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
    closed: 'bg-muted/20 text-muted border-border',
  }[status] || 'bg-muted/20 text-muted border-border';

  return (
    <span className={`text-xs px-3 py-1 rounded-full border font-medium ${className}`}>
      {status?.replace('_', ' ') || 'open'}
    </span>
  );
}

export default function CustomerDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [tickets, setTickets] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [context, setContext] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [contextFilter, setContextFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  useEffect(() => {
    setPage(1); // Reset to page 1 when filters change
  }, [statusFilter, contextFilter, dateFrom, dateTo, searchQuery]);

  useEffect(() => {
    loadTickets();
  }, [statusFilter, contextFilter, dateFrom, dateTo, searchQuery, page, pageSize]);

  const loadTickets = async () => {
    setLoading(true);
    const filters = {
      ...(searchQuery && { search: searchQuery }),
      ...(statusFilter && { status: statusFilter }),
      ...(contextFilter && { context: contextFilter }),
      ...(dateFrom && { date_from: dateFrom }),
      ...(dateTo && { date_to: dateTo }),
      page,
      page_size: pageSize,
    };
    const { data, error } = await getCustomerTickets(filters);
    if (!error && data) {
      setTickets(data.tickets || []);
      setPagination(data.pagination || null);
    }
    setLoading(false);
  };

  const clearFilters = () => {
    setSearchQuery('');
    setStatusFilter('');
    setContextFilter('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const handleCreateTicket = async () => {
    if (!context.trim() || !subject.trim() || !message.trim()) {
      alert('Please fill in all fields');
      return;
    }

    setCreating(true);
    const { data, error } = await createTicket(context.trim(), subject.trim(), message.trim());

    if (error) {
      alert(`Failed to create ticket: ${error}`);
    } else if (data?.ticket_id) {
      navigate(`/customer/ticket/${data.ticket_id}`);
      setContext('');
      setSubject('');
      setMessage('');
    }
    setCreating(false);
    loadTickets();
  };

  return (
    <div className="min-h-screen bg-bg text-text">
      {/* Header */}
      <header className="glass border-b border-border px-6 py-4 sticky top-0 z-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center glow">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <div className="flex flex-col">
                <div className="text-lg font-bold gradient-text">Nexus</div>
                <div className="flex items-center gap-2 text-sm text-muted">
                  <span>Hello {user?.email || user?.name}</span>
                  <span className="px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-xs uppercase font-medium tracking-wide">
                    {user?.role?.replace('_', ' ')}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <button
            onClick={logout}
            className="px-4 py-2 bg-red-500/10 text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/20 transition-all text-sm font-medium"
          >
            Logout
          </button>
        </div>
      </header>

      <div className="flex h-[calc(100vh-73px)]">
        {/* Sidebar */}
        <aside className="w-80 glass border-r border-border p-6 overflow-y-auto">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-text mb-4">New Ticket</h2>
            <div className="space-y-3">
              <input
                type="text"
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="Context (e.g., Product Issue)"
                className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text placeholder-muted focus:outline-none focus:ring-2 focus:ring-accent hover:border-accent/50 transition-all"
              />
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Subject"
                className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text placeholder-muted focus:outline-none focus:ring-2 focus:ring-accent hover:border-accent/50 transition-all"
              />
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Message"
                rows={3}
                className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text placeholder-muted focus:outline-none focus:ring-2 focus:ring-accent hover:border-accent/50 transition-all resize-none"
              />
              <button
                onClick={handleCreateTicket}
                disabled={creating || !context.trim() || !subject.trim() || !message.trim()}
                className="w-full py-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold rounded-lg hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-indigo-500/30 glow-hover"
              >
                {creating ? 'Creating...' : 'Create Ticket'}
              </button>
            </div>
          </div>

          {/* Search */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-muted mb-3 uppercase tracking-wide">Search</h3>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tickets..."
              className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text placeholder-muted focus:outline-none focus:ring-2 focus:ring-accent hover:border-accent/50 transition-all"
            />
          </div>

          {/* Filters */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-muted uppercase tracking-wide">Filters</h3>
              <button
                onClick={() => setShowFilters(!showFilters)}
                className="text-xs text-accent hover:text-accent-hover transition-colors"
              >
                {showFilters ? 'Hide' : 'Show'}
              </button>
            </div>

            {showFilters && (
              <div className="space-y-3">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent hover:border-accent/50 transition-all"
                >
                  <option value="">All Statuses</option>
                  <option value="open">Open</option>
                  <option value="human_assigned">Assigned</option>
                  <option value="closed">Closed</option>
                </select>

                <input
                  type="text"
                  value={contextFilter}
                  onChange={(e) => setContextFilter(e.target.value)}
                  placeholder="Context/Brand"
                  className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text placeholder-muted focus:outline-none focus:ring-2 focus:ring-accent hover:border-accent/50 transition-all"
                />

                <div className="space-y-2">
                  <label className="text-xs text-muted">Date From</label>
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent hover:border-accent/50 transition-all"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs text-muted">Date To</label>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent hover:border-accent/50 transition-all"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs text-muted">Items per page</label>
                  <select
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value));
                      setPage(1);
                    }}
                    className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent hover:border-accent/50 transition-all"
                  >
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                  </select>
                </div>

                <button
                  onClick={clearFilters}
                  className="w-full px-4 py-2 bg-panel-hover text-text-secondary rounded-lg hover:bg-panel-hover hover:text-text transition-all text-sm border border-border"
                >
                  Clear Filters
                </button>
              </div>
            )}
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-6 overflow-y-auto">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-text mb-2">My Tickets</h2>
              <p className="text-sm text-muted">Manage and track your support tickets</p>
            </div>
            {pagination && (
              <div className="text-sm text-muted">
                Showing {tickets.length > 0 ? (page - 1) * pageSize + 1 : 0} - {Math.min(page * pageSize, pagination.total_count)} of {pagination.total_count} tickets
              </div>
            )}
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loading />
            </div>
          ) : tickets.length === 0 ? (
            <div className="text-center py-12 text-muted">
              <p className="text-lg mb-2">No tickets yet</p>
              <p className="text-sm">Create a new ticket to get started</p>
            </div>
          ) : (
            <div className="space-y-3">
              {tickets.map((ticket) => (
                <div
                  key={ticket.id}
                  onClick={() => navigate(`/customer/ticket/${ticket.id}`)}
                  className="glass border border-border rounded-lg p-4 hover:border-accent/50 hover:bg-panel-hover cursor-pointer transition-all hover-lift"
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-lg font-semibold text-text">{ticket.subject}</h3>
                    <Badge status={ticket.status} />
                  </div>
                  <p className="text-sm text-text-secondary mb-2">{ticket.context}</p>
                  <p className="text-xs text-muted">
                    Created: {new Date(ticket.created_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {pagination && pagination.total_pages > 0 && (
            <div className="mt-6 flex items-center justify-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={!pagination.has_prev || loading}
                className="px-4 py-2 glass border border-border rounded-lg text-text hover:bg-panel-hover disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                Previous
              </button>
              <div className="flex items-center gap-2">
                {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                  let pageNum;
                  if (pagination.total_pages <= 5) {
                    pageNum = i + 1;
                  } else if (pagination.page <= 3) {
                    pageNum = i + 1;
                  } else if (pagination.page >= pagination.total_pages - 2) {
                    pageNum = pagination.total_pages - 4 + i;
                  } else {
                    pageNum = pagination.page - 2 + i;
                  }
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setPage(pageNum)}
                      disabled={loading}
                      className={`px-4 py-2 rounded-lg transition-all ${pageNum === pagination.page
                          ? 'bg-accent text-white glow'
                          : 'glass border border-border text-text hover:bg-panel-hover'
                        } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {pageNum}
                    </button>
                  );
                })}
              </div>
              <button
                onClick={() => setPage(p => Math.min(pagination.total_pages, p + 1))}
                disabled={!pagination.has_next || loading}
                className="px-4 py-2 glass border border-border rounded-lg text-text hover:bg-panel-hover disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                Next
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

