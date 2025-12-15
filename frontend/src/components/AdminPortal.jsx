import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import AdminDashboard from './admin/AdminDashboard';
import AdminTicketView from './admin/AdminTicketView';
import EmailAccountManager from './admin/EmailAccountManager';
import EmailTemplateManager from './admin/EmailTemplateManager';
import TrashView from './admin/TrashView';
import OrganizationManager from './admin/OrganizationManager';
import RoutingRulesManager from './admin/RoutingRulesManager';
import TagsCategoriesManager from './admin/TagsCategoriesManager';

export default function AdminPortal() {
  const { user, isAuthenticated, isAdmin, isSuperAdmin, logout } = useAuth();
  const location = useLocation();

  if (!isAuthenticated || !isAdmin) {
    return <Navigate to="/login" replace />;
  }

  const isActive = (path) => location.pathname === path;

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Navigation Header */}
      <header className="glass border-b border-border px-6 py-4 sticky top-0 z-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link to="/admin" className="flex items-center gap-3 group">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center glow">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <span className="text-xl font-bold gradient-text">Nexus</span>
              <span className="text-sm text-muted font-medium">Admin</span>
            </Link>
            <nav className="flex items-center gap-2">
              <Link
                to="/admin"
                className={`px-4 py-2 rounded-lg transition-all text-sm font-medium ${isActive('/admin') || isActive('/admin/')
                  ? 'bg-accent/20 text-accent border border-accent/30'
                  : 'text-text-secondary hover:text-text hover:bg-panel-hover border border-transparent'
                  }`}
              >
                Tickets
              </Link>
              <Link
                to="/admin/email-accounts"
                className={`px-4 py-2 rounded-lg transition-all text-sm font-medium ${isActive('/admin/email-accounts')
                  ? 'bg-accent/20 text-accent border border-accent/30'
                  : 'text-text-secondary hover:text-text hover:bg-panel-hover border border-transparent'
                  }`}
              >
                Email Accounts
              </Link>
              <Link
                to="/admin/email-templates"
                className={`px-4 py-2 rounded-lg transition-all text-sm font-medium ${isActive('/admin/email-templates')
                  ? 'bg-accent/20 text-accent border border-accent/30'
                  : 'text-text-secondary hover:text-text hover:bg-panel-hover border border-transparent'
                  }`}
              >
                Email Templates
              </Link>
              <Link
                to="/admin/trash"
                className={`px-4 py-2 rounded-lg transition-all text-sm font-medium ${isActive('/admin/trash')
                  ? 'bg-accent/20 text-accent border border-accent/30'
                  : 'text-text-secondary hover:text-text hover:bg-panel-hover border border-transparent'
                  }`}
              >
                Trash
              </Link>
              <Link
                to="/admin/routing-rules"
                className={`px-4 py-2 rounded-lg transition-all text-sm font-medium ${isActive('/admin/routing-rules')
                  ? 'bg-accent/20 text-accent border border-accent/30'
                  : 'text-text-secondary hover:text-text hover:bg-panel-hover border border-transparent'
                  }`}
              >
                Routing Rules
              </Link>
              <Link
                to="/admin/tags-categories"
                className={`px-4 py-2 rounded-lg transition-all text-sm font-medium ${isActive('/admin/tags-categories')
                  ? 'bg-accent/20 text-accent border border-accent/30'
                  : 'text-text-secondary hover:text-text hover:bg-panel-hover border border-transparent'
                  }`}
              >
                Tags & Categories
              </Link>
              {isSuperAdmin && (
                <Link
                  to="/admin/organizations"
                  className={`px-4 py-2 rounded-lg transition-all text-sm font-medium ${isActive('/admin/organizations')
                    ? 'bg-accent/20 text-accent border border-accent/30'
                    : 'text-text-secondary hover:text-text hover:bg-panel-hover border border-transparent'
                    }`}
                >
                  Organizations
                </Link>
              )}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right hidden md:block">
              <div className="text-sm font-medium text-text">Hello {user?.email || user?.name}</div>
              <div className="text-xs text-muted uppercase tracking-wider">{user?.role?.replace('_', ' ')}</div>
            </div>
            <button
              onClick={logout}
              className="px-4 py-2 bg-red-500/10 text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/20 transition-all text-sm font-medium"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<AdminDashboard />} />
          <Route path="/ticket/:ticketId" element={<AdminTicketView />} />
          <Route path="/email-accounts" element={<EmailAccountManager />} />
          <Route path="/email-templates" element={<EmailTemplateManager />} />
          <Route path="/trash" element={<TrashView />} />
          <Route path="/routing-rules" element={<RoutingRulesManager />} />
          <Route path="/tags-categories" element={<TagsCategoriesManager />} />
          {isSuperAdmin && (
            <Route path="/organizations" element={<OrganizationManager />} />
          )}
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </div>
    </div>
  );
}
