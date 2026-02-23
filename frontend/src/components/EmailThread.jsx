import { useState, useEffect } from 'react';
import { getTicketEmailThread } from '../services/api';
import Loading from './Loading';

function formatTimestamp(timestamp) {
  if (!timestamp) return '';
  try {
    const date = new Date(timestamp);
    return date.toLocaleString();
  } catch {
    return timestamp;
  }
}

function EmailBubble({ email }) {
  const isInbound = email.direction === 'inbound';

  return (
    <div className={`max-w-[80%] mb-4 ${isInbound ? 'mr-auto' : 'ml-auto'}`}>
      <div
        className={`p-4 rounded-lg border ${isInbound
            ? 'bg-gray-800 border-gray-700 text-white'
            : 'bg-blue-500/20 border-blue-500/50 text-white'
          }`}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-semibold uppercase ${isInbound ? 'text-gray-300' : 'text-blue-300'
              }`}>
              {isInbound ? '📥 Inbound' : '📤 Outbound'}
            </span>
            <span className="text-xs text-gray-400">{email.from_email}</span>
          </div>
          <span className="text-xs text-gray-500">{formatTimestamp(email.created_at)}</span>
        </div>

        <div className="mb-2">
          <div className="text-sm font-semibold text-white mb-1">{email.subject}</div>
          <div className="text-xs text-gray-400">
            To: {Array.isArray(email.to_email) ? email.to_email.join(', ') : email.to_email}
            {email.cc_email && email.cc_email.length > 0 && (
              <span className="ml-2">CC: {email.cc_email.join(', ')}</span>
            )}
          </div>
        </div>

        {email.body_html ? (
          <div className="mt-4 bg-white rounded overflow-hidden shadow-inner max-w-full">
            <iframe
              sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"
              srcDoc={email.body_html}
              className="w-full h-[500px] border-0"
              title="Email body"
            />
          </div>
        ) : (
          <div className="mt-4 text-sm whitespace-pre-wrap leading-relaxed bg-black/20 p-4 rounded-md border border-white/10 max-h-[500px] overflow-y-auto">
            {email.body_text}
          </div>
        )}

        {email.has_attachments && (
          <div className="mt-2 text-xs text-gray-400">
            📎 This email has attachments
          </div>
        )}

        {email.status === 'failed' && email.error_message && (
          <div className="mt-2 text-xs text-red-400 bg-red-500/20 border border-red-500/50 rounded px-2 py-1">
            Error: {email.error_message}
          </div>
        )}
      </div>
    </div>
  );
}

export default function EmailThread({ ticketId }) {
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadEmails();
  }, [ticketId]);

  const loadEmails = async () => {
    setLoading(true);
    setError(null);
    const { data, error: loadError } = await getTicketEmailThread(ticketId);

    if (loadError) {
      setError(loadError);
    } else if (data) {
      setEmails(data.emails || []);
    }
    setLoading(false);
  };

  if (loading) {
    return <Loading />;
  }

  if (error) {
    return (
      <div className="text-red-400 text-sm">
        Failed to load emails: {error}
      </div>
    );
  }

  if (emails.length === 0) {
    return (
      <div className="text-center text-gray-400 py-8">
        <div className="text-4xl mb-2">📧</div>
        <p>No emails in this ticket</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">
          Email Thread ({emails.length})
        </h3>
        <button
          onClick={loadEmails}
          className="text-sm text-gray-400 hover:text-white transition-colors"
        >
          🔄 Refresh
        </button>
      </div>

      {emails.map((email, idx) => (
        <EmailBubble key={email.id || idx} email={email} />
      ))}
    </div>
  );
}

