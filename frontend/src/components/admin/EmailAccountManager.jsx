import { useState, useEffect } from 'react';
import {
  listEmailAccounts,
  createEmailAccount,
  testEmailAccount,
  testImapConnection,
  enableEmailPolling,
  disableEmailPolling,
  getPollingStatus,
  pollEmailAccount
} from '../../services/api';
import Loading from '../Loading';

export default function EmailAccountManager() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingAccount, setEditingAccount] = useState(null);
  const [testing, setTesting] = useState({});
  const [testingImap, setTestingImap] = useState({});
  const [pollingStatus, setPollingStatus] = useState({});
  const [togglingPolling, setTogglingPolling] = useState({});
  const [pollingNow, setPollingNow] = useState({});

  const [formData, setFormData] = useState({
    email: '',
    display_name: '',
    provider: 'smtp',
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    api_key: '',
    credentials: null,
    is_active: true,
    is_default: false,
    imap_host: '',
    imap_port: 993,
    imap_enabled: false,
  });

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    // Load polling status for all accounts
    const loadPollingStatus = async () => {
      if (accounts.length > 0) {
        const statusPromises = accounts.map(async (account) => {
          const { data } = await getPollingStatus(account.id);
          return { accountId: account.id, status: data };
        });
        const statuses = await Promise.all(statusPromises);
        const statusMap = {};
        statuses.forEach(({ accountId, status }) => {
          if (status) {
            statusMap[accountId] = status;
          }
        });
        setPollingStatus(statusMap);
      }
    };
    if (accounts.length > 0) {
      loadPollingStatus();
    }
  }, [accounts]);

  const loadAccounts = async () => {
    setLoading(true);
    const { data, error } = await listEmailAccounts();
    if (error) {
      alert(`Failed to load email accounts: ${error}`);
    } else if (data) {
      setAccounts(data.accounts || []);
    }
    setLoading(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const { data, error } = await createEmailAccount(formData);

    if (error) {
      alert(`Failed to save email account: ${error}`);
    } else {
      await loadAccounts();
      setShowForm(false);
      resetForm();
    }
  };

  const handleTest = async (accountId) => {
    setTesting({ ...testing, [accountId]: true });
    const { data, error } = await testEmailAccount(accountId);

    if (error) {
      alert(`Connection test failed: ${error}`);
    } else {
      alert(`Connection test successful: ${data.message}`);
    }

    setTesting({ ...testing, [accountId]: false });
  };

  const handleTestImap = async (accountId) => {
    setTestingImap({ ...testingImap, [accountId]: true });
    const { data, error } = await testImapConnection(accountId);

    if (error) {
      alert(`IMAP connection test failed: ${error}`);
    } else {
      alert(`IMAP connection test successful: ${data.message}`);
    }

    setTestingImap({ ...testingImap, [accountId]: false });
  };

  const handleTogglePolling = async (accountId, enable) => {
    setTogglingPolling({ ...togglingPolling, [accountId]: true });

    const { data, error } = enable
      ? await enableEmailPolling(accountId)
      : await disableEmailPolling(accountId);

    if (error) {
      alert(`Failed to ${enable ? 'enable' : 'disable'} polling: ${error}`);
    } else {
      await loadAccounts();
      // Reload polling status
      const { data: statusData } = await getPollingStatus(accountId);
      if (statusData) {
        setPollingStatus({ ...pollingStatus, [accountId]: statusData });
      }
      alert(`Email polling ${enable ? 'enabled' : 'disabled'} successfully`);
    }

    setTogglingPolling({ ...togglingPolling, [accountId]: false });
  };

  const handlePollAccount = async (accountId) => {
    setPollingNow({ ...pollingNow, [accountId]: true });

    const { data, error } = await pollEmailAccount(accountId);

    if (error) {
      alert(`Failed to fetch emails: ${error}`);
    } else {
      await loadAccounts();
      const { data: statusData } = await getPollingStatus(accountId);
      if (statusData) {
        setPollingStatus({ ...pollingStatus, [accountId]: statusData });
      }
      alert(`Successfully polled: ${data.emails_fetched || 0} fetched, ${data.tickets_created || 0} tickets created.`);
    }

    setPollingNow({ ...pollingNow, [accountId]: false });
  };

  const handleEdit = (account) => {
    setEditingAccount(account);
    setFormData({
      email: account.email,
      display_name: account.display_name || '',
      provider: account.provider,
      smtp_host: account.smtp_host || '',
      smtp_port: account.smtp_port || 587,
      smtp_username: account.smtp_username || '',
      smtp_password: '', // Don't show password
      api_key: '', // Don't show API key
      credentials: null,
      is_active: account.is_active,
      is_default: account.is_default,
      imap_host: account.imap_host || '',
      imap_port: account.imap_port || 993,
      imap_enabled: account.imap_enabled || false,
    });
    setShowForm(true);
  };

  const resetForm = () => {
    setFormData({
      email: '',
      display_name: '',
      provider: 'smtp',
      smtp_host: '',
      smtp_port: 587,
      smtp_username: '',
      smtp_password: '',
      api_key: '',
      credentials: null,
      is_active: true,
      is_default: false,
      imap_host: '',
      imap_port: 993,
      imap_enabled: false,
    });
    setEditingAccount(null);
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch {
      return dateString;
    }
  };

  if (loading) {
    return <Loading />;
  }

  return (
    <div className="min-h-screen bg-bg text-text p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold gradient-text">Email Accounts</h2>
          <button
            onClick={() => {
              resetForm();
              setShowForm(!showForm);
            }}
            className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover transition-all glow-hover"
          >
            {showForm ? 'Cancel' : '+ Add Email Account'}
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleSubmit} className="glass border border-border rounded-lg p-6 space-y-4">
            <h3 className="text-lg font-semibold text-text">
              {editingAccount ? 'Edit Email Account' : 'New Email Account'}
            </h3>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Email Address *
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  required
                  className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Display Name
                </label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                  className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Provider *
              </label>
              <select
                value={formData.provider}
                onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                required
                className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent"
              >
                <option value="smtp">SMTP</option>
                <option value="sendgrid">SendGrid</option>
                <option value="ses">AWS SES</option>
                <option value="mailgun">Mailgun</option>
                <option value="other">Other</option>
              </select>
            </div>

            {formData.provider === 'smtp' && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-2">
                      SMTP Host *
                    </label>
                    <input
                      type="text"
                      value={formData.smtp_host}
                      onChange={(e) => setFormData({ ...formData, smtp_host: e.target.value })}
                      placeholder="smtp.gmail.com"
                      required
                      className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-2">
                      SMTP Port *
                    </label>
                    <input
                      type="number"
                      value={formData.smtp_port}
                      onChange={(e) => setFormData({ ...formData, smtp_port: parseInt(e.target.value) })}
                      required
                      className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-2">
                      SMTP Username *
                    </label>
                    <input
                      type="text"
                      value={formData.smtp_username}
                      onChange={(e) => setFormData({ ...formData, smtp_username: e.target.value })}
                      required
                      className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-2">
                      SMTP Password *
                    </label>
                    <input
                      type="password"
                      value={formData.smtp_password}
                      onChange={(e) => setFormData({ ...formData, smtp_password: e.target.value })}
                      required={!editingAccount}
                      placeholder={editingAccount ? "Leave blank to keep current" : ""}
                      className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent"
                    />
                  </div>
                </div>
              </>
            )}

            {formData.provider === 'sendgrid' && (
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  SendGrid API Key *
                </label>
                <input
                  type="password"
                  value={formData.api_key}
                  onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                  required={!editingAccount}
                  placeholder={editingAccount ? "Leave blank to keep current" : ""}
                  className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent"
                />
              </div>
            )}

            {formData.provider === 'smtp' && (
              <div className="border-t border-border pt-4 mt-4">
                <h4 className="text-sm font-semibold text-text mb-3">IMAP Polling Settings</h4>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-text-secondary mb-2">
                        IMAP Host
                      </label>
                      <input
                        type="text"
                        value={formData.imap_host}
                        onChange={(e) => setFormData({ ...formData, imap_host: e.target.value })}
                        placeholder="Auto-detected for Gmail/Outlook"
                        className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent"
                      />
                      <p className="text-xs text-text-secondary mt-1">
                        Leave blank for auto-detection (Gmail/Outlook)
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-text-secondary mb-2">
                        IMAP Port
                      </label>
                      <input
                        type="number"
                        value={formData.imap_port}
                        onChange={(e) => setFormData({ ...formData, imap_port: parseInt(e.target.value) || 993 })}
                        placeholder="993"
                        className="w-full px-4 py-2 bg-panel border border-border rounded-lg text-text focus:outline-none focus:ring-2 focus:ring-accent"
                      />
                    </div>
                  </div>

                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.imap_enabled}
                      onChange={(e) => setFormData({ ...formData, imap_enabled: e.target.checked })}
                      className="w-4 h-4 text-accent bg-panel border-border rounded focus:ring-accent"
                    />
                    <span className="text-sm text-text-secondary">
                      Enable automatic email polling (creates tickets from incoming emails)
                    </span>
                  </label>
                </div>
              </div>
            )}

            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="w-4 h-4 text-accent bg-panel border-border rounded focus:ring-accent"
                />
                <span className="text-sm text-text-secondary">Active</span>
              </label>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.is_default}
                  onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                  className="w-4 h-4 text-accent bg-panel border-border rounded focus:ring-accent"
                />
                <span className="text-sm text-text-secondary">Default</span>
              </label>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                className="px-6 py-2 bg-accent text-white font-semibold rounded-lg hover:bg-accent-hover transition-all"
              >
                {editingAccount ? 'Update' : 'Create'} Account
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  resetForm();
                }}
                className="px-6 py-2 glass border border-border text-text font-semibold rounded-lg hover:bg-panel-hover transition-all"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        <div className="space-y-3">
          {accounts.length === 0 ? (
            <div className="text-center text-muted py-8">
              <p>No email accounts configured</p>
            </div>
          ) : (
            accounts.map((account) => (
              <div
                key={account.id}
                className="glass border border-border rounded-lg p-4 flex items-center justify-between"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-lg font-semibold text-text">
                      {account.display_name || account.email}
                    </span>
                    {account.is_default && (
                      <span className="text-xs bg-orange-500/20 text-orange-400 px-2 py-1 rounded">
                        Default
                      </span>
                    )}
                    {account.is_active ? (
                      <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded">
                        Active
                      </span>
                    ) : (
                      <span className="text-xs bg-gray-500/20 text-gray-400 px-2 py-1 rounded">
                        Inactive
                      </span>
                    )}
                    {account.imap_enabled && account.is_active && (
                      <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-1 rounded">
                        Polling Enabled
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-text-secondary mt-1">
                    {account.email} • {account.provider.toUpperCase()}
                  </div>
                  {account.imap_enabled && pollingStatus[account.id] && (
                    <div className="text-xs text-text-secondary mt-1">
                      Last polled: {formatDate(pollingStatus[account.id]?.last_polled_at)}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  {account.provider === 'smtp' && (
                    <>
                      <button
                        onClick={() => handleTestImap(account.id)}
                        disabled={testingImap[account.id]}
                        className="px-3 py-1.5 text-xs bg-purple-500/10 text-purple-400 border border-purple-500/30 rounded hover:bg-purple-500/20 disabled:opacity-50 transition-all"
                        title="Test IMAP connection"
                      >
                        {testingImap[account.id] ? 'Testing IMAP...' : 'Test IMAP'}
                      </button>
                      {account.imap_enabled ? (
                        <button
                          onClick={() => handleTogglePolling(account.id, false)}
                          disabled={togglingPolling[account.id] || !account.is_active}
                          className="px-3 py-1.5 text-xs bg-red-500/10 text-red-400 border border-red-500/30 rounded hover:bg-red-500/20 disabled:opacity-50 transition-all"
                          title="Disable email polling"
                        >
                          {togglingPolling[account.id] ? 'Disabling...' : 'Disable Polling'}
                        </button>
                      ) : (
                        <button
                          onClick={() => handleTogglePolling(account.id, true)}
                          disabled={togglingPolling[account.id] || !account.is_active}
                          className="px-3 py-1.5 text-xs bg-green-500/10 text-green-400 border border-green-500/30 rounded hover:bg-green-500/20 disabled:opacity-50 transition-all"
                          title="Enable email polling"
                        >
                          {togglingPolling[account.id] ? 'Enabling...' : 'Enable Polling'}
                        </button>
                      )}
                      {account.imap_enabled && (
                        <button
                          onClick={() => handlePollAccount(account.id)}
                          disabled={pollingNow[account.id] || !account.is_active}
                          className="px-3 py-1.5 text-xs bg-orange-500/10 text-orange-400 border border-orange-500/30 rounded hover:bg-orange-500/20 disabled:opacity-50 transition-all"
                          title="Fetch emails now"
                        >
                          {pollingNow[account.id] ? 'Fetching...' : 'Fetch Emails'}
                        </button>
                      )}
                    </>
                  )}
                  <button
                    onClick={() => handleTest(account.id)}
                    disabled={testing[account.id]}
                    className="px-3 py-1.5 text-xs bg-blue-500/10 text-blue-400 border border-blue-500/30 rounded hover:bg-blue-500/20 disabled:opacity-50 transition-all"
                    title="Test SMTP connection"
                  >
                    {testing[account.id] ? 'Testing...' : 'Test SMTP'}
                  </button>
                  <button
                    onClick={() => handleEdit(account)}
                    className="px-3 py-1.5 text-xs glass border border-border text-text rounded hover:bg-panel-hover transition-all"
                  >
                    Edit
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

