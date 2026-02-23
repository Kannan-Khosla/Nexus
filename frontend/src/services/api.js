/**
 * API service for interacting with the FastAPI backend
 */

import { getToken } from './auth';

const DEFAULT_BASE_URL = 'http://localhost:8000';

/**
 * Get base URL from localStorage or use default
 */
export function getBaseUrl() {
  return localStorage.getItem('baseUrl') || DEFAULT_BASE_URL;
}

/**
 * Set base URL
 */
export function setBaseUrl(url) {
  localStorage.setItem('baseUrl', url);
}

/**
 * Get admin token from localStorage
 */
function getAdminToken() {
  return localStorage.getItem('adminToken') || '';
}

/**
 * Set admin token
 */
export function setAdminToken(token) {
  localStorage.setItem('adminToken', token);
}

/**
 * Make API request with error handling and JWT authentication
 */
async function apiRequest(url, options = {}) {
  const baseUrl = getBaseUrl().replace(/\/+$/, '');
  const fullUrl = `${baseUrl}${url}`;
  const token = getToken();

  try {
    const response = await fetch(fullUrl, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    });

    const data = await response.json();

    if (!response.ok) {
      // Handle 401 Unauthorized
      if (response.status === 401) {
        throw new Error('Authentication required. Please login.');
      }
      throw new Error(data.detail || data.error || `HTTP ${response.status}`);
    }

    return { data, error: null };
  } catch (error) {
    return { data: null, error: error.message || 'Request failed' };
  }
}

// Auth
export const login = async (email, password) => {
  const { data, error } = await apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  return { data, error: error || null };
};

export const register = async (email, password, name) => {
  const { data, error } = await apiRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, name }),
  });
  return { data, error: error || null };
};

export const forgotPassword = async (email) => {
  const { data, error } = await apiRequest('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
  return { data, error: error || null };
};

export const resetPassword = async (token, newPassword) => {
  const { data, error } = await apiRequest('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({
      token,
      new_password: newPassword
    }),
  });
  return { data, error: error || null };
};

/**
 * List all tickets (admin) with search, filters, and pagination
 */
export async function listTickets(filters = {}) {
  const params = new URLSearchParams();
  if (filters.search) params.append('search', filters.search);
  if (filters.status) params.append('status', filters.status);
  if (filters.context) params.append('context', filters.context);
  if (filters.assigned_to) params.append('assigned_to', filters.assigned_to);
  if (filters.date_from) params.append('date_from', filters.date_from);
  if (filters.date_to) params.append('date_to', filters.date_to);
  if (filters.page) params.append('page', filters.page);
  if (filters.page_size) params.append('page_size', filters.page_size);

  const queryString = params.toString();
  const url = `/admin/tickets${queryString ? `?${queryString}` : ''}`;
  return apiRequest(url);
}

/**
 * Get ticket thread
 */
export async function getTicket(ticketId) {
  return apiRequest(`/ticket/${encodeURIComponent(ticketId)}`);
}

/**
 * Create or continue ticket
 */
export async function createTicket(context, subject, message) {
  return apiRequest('/ticket', {
    method: 'POST',
    body: JSON.stringify({ context, subject, message }),
  });
}

/**
 * Get customer tickets with search, filters, and pagination
 */
export async function getCustomerTickets(filters = {}) {
  const params = new URLSearchParams();
  if (filters.search) params.append('search', filters.search);
  if (filters.status) params.append('status', filters.status);
  if (filters.context) params.append('context', filters.context);
  if (filters.date_from) params.append('date_from', filters.date_from);
  if (filters.date_to) params.append('date_to', filters.date_to);
  if (filters.page) params.append('page', filters.page);
  if (filters.page_size) params.append('page_size', filters.page_size);

  const queryString = params.toString();
  const url = `/customer/tickets${queryString ? `?${queryString}` : ''}`;
  return apiRequest(url);
}

/**
 * Rate an AI response
 */
export async function rateResponse(ticketId, messageId, rating) {
  return apiRequest(`/ticket/${encodeURIComponent(ticketId)}/rate`, {
    method: 'POST',
    body: JSON.stringify({ message_id: messageId, rating }),
  });
}

/**
 * Escalate to human
 */
export async function escalateToHuman(ticketId, reason = null) {
  return apiRequest(`/ticket/${encodeURIComponent(ticketId)}/escalate`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

/**
 * Admin reply to ticket
 */
export async function adminReply(ticketId, message) {
  return apiRequest(`/ticket/${encodeURIComponent(ticketId)}/admin/reply`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

/**
 * Assign ticket to admin
 */
export async function assignTicketToAdmin(ticketId, adminEmail) {
  return apiRequest(`/admin/ticket/${encodeURIComponent(ticketId)}/assign-admin`, {
    method: 'POST',
    body: JSON.stringify({ admin_email: adminEmail }),
  });
}

/**
 * Get assigned tickets for admin with search, filters, and pagination
 */
export async function getAssignedTickets(filters = {}) {
  const params = new URLSearchParams();
  if (filters.search) params.append('search', filters.search);
  if (filters.status) params.append('status', filters.status);
  if (filters.context) params.append('context', filters.context);
  if (filters.date_from) params.append('date_from', filters.date_from);
  if (filters.date_to) params.append('date_to', filters.date_to);
  if (filters.page) params.append('page', filters.page);
  if (filters.page_size) params.append('page_size', filters.page_size);

  const queryString = params.toString();
  const url = `/admin/tickets/assigned${queryString ? `?${queryString}` : ''}`;
  return apiRequest(url);
}

/**
 * Send reply to ticket
 */
export async function sendReply(ticketId, message) {
  return apiRequest(`/ticket/${encodeURIComponent(ticketId)}/reply`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

/**
 * Assign agent to ticket
 */
export async function assignAgent(ticketId, agentName) {
  const token = getAdminToken();
  return apiRequest(
    `/admin/ticket/${encodeURIComponent(ticketId)}/assign?agent_name=${encodeURIComponent(agentName)}`,
    {
      method: 'POST',
      headers: token ? { 'X-Admin-Token': token } : {},
    }
  );
}

/**
 * Close ticket
 */
export async function closeTicket(ticketId) {
  const token = getAdminToken();
  return apiRequest(`/admin/ticket/${encodeURIComponent(ticketId)}/close`, {
    method: 'POST',
    headers: token ? { 'X-Admin-Token': token } : {},
  });
}

/**
 * Get statistics
 */
export async function getStats() {
  return apiRequest('/stats');
}

/**
 * Upload attachment to ticket
 */
export async function uploadAttachment(ticketId, file, messageId = null) {
  const baseUrl = getBaseUrl().replace(/\/+$/, '');
  const fullUrl = `${baseUrl}/ticket/${encodeURIComponent(ticketId)}/attachments`;
  const token = getToken();

  const formData = new FormData();
  formData.append('file', file);
  if (messageId) {
    formData.append('message_id', messageId);
  }

  try {
    const response = await fetch(fullUrl, {
      method: 'POST',
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please login.');
      }
      throw new Error(data.detail || data.error || `HTTP ${response.status}`);
    }

    return { data, error: null };
  } catch (error) {
    return { data: null, error: error.message || 'Upload failed' };
  }
}

/**
 * List attachments for a ticket
 */
export async function listAttachments(ticketId, messageId = null) {
  const params = new URLSearchParams();
  if (messageId) params.append('message_id', messageId);

  const queryString = params.toString();
  const url = `/ticket/${encodeURIComponent(ticketId)}/attachments${queryString ? `?${queryString}` : ''}`;
  return apiRequest(url);
}

/**
 * Download attachment
 */
export async function downloadAttachment(attachmentId) {
  const baseUrl = getBaseUrl().replace(/\/+$/, '');
  const fullUrl = `${baseUrl}/attachment/${encodeURIComponent(attachmentId)}`;
  const token = getToken();

  try {
    const response = await fetch(fullUrl, {
      method: 'GET',
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please login.');
      }
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.error || `HTTP ${response.status}`);
    }

    // Get filename from Content-Disposition header
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = `attachment-${attachmentId}`;
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
      if (filenameMatch) {
        filename = filenameMatch[1];
      }
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

    return { data: { success: true }, error: null };
  } catch (error) {
    return { data: null, error: error.message || 'Download failed' };
  }
}

/**
 * Delete attachment
 */
export async function deleteAttachment(attachmentId) {
  return apiRequest(`/attachment/${encodeURIComponent(attachmentId)}`, {
    method: 'DELETE',
  });
}

/**
 * Email Account Management
 */

/**
 * Create or update email account
 */
export async function createEmailAccount(accountData) {
  return apiRequest('/admin/email-accounts', {
    method: 'POST',
    body: JSON.stringify(accountData),
  });
}

/**
 * List all email accounts
 */
export async function listEmailAccounts() {
  return apiRequest('/admin/email-accounts');
}

/**
 * Test email account connection
 */
export async function testEmailAccount(accountId) {
  return apiRequest(`/admin/email-accounts/${encodeURIComponent(accountId)}/test`, {
    method: 'POST',
  });
}

/**
 * Test IMAP connection for an email account
 */
export async function testImapConnection(accountId) {
  return apiRequest(`/admin/email-accounts/${encodeURIComponent(accountId)}/test-imap`, {
    method: 'POST',
  });
}

/**
 * Enable email polling for an account
 */
export async function enableEmailPolling(accountId) {
  return apiRequest(`/admin/email-accounts/${encodeURIComponent(accountId)}/enable-polling`, {
    method: 'POST',
  });
}

/**
 * Disable email polling for an account
 */
export async function disableEmailPolling(accountId) {
  return apiRequest(`/admin/email-accounts/${encodeURIComponent(accountId)}/disable-polling`, {
    method: 'POST',
  });
}

/**
 * Get polling status for an email account
 */
export async function getPollingStatus(accountId) {
  return apiRequest(`/admin/email-accounts/${encodeURIComponent(accountId)}/polling-status`);
}

/**
 * Manually poll an email account
 */
export async function pollEmailAccount(accountId) {
  return apiRequest(`/admin/email-accounts/${encodeURIComponent(accountId)}/poll-now`, {
    method: 'POST',
  });
}

/**
 * Send email from ticket
 */
export async function sendEmailFromTicket(ticketId, emailData) {
  return apiRequest(`/ticket/${encodeURIComponent(ticketId)}/send-email`, {
    method: 'POST',
    body: JSON.stringify(emailData),
  });
}

/**
 * Get email thread for ticket
 */
export async function getTicketEmailThread(ticketId) {
  return apiRequest(`/ticket/${encodeURIComponent(ticketId)}/emails`);
}

/**
 * Email Templates
 */

/**
 * Create or update email template
 */
export async function createEmailTemplate(templateData) {
  return apiRequest('/admin/email-templates', {
    method: 'POST',
    body: JSON.stringify(templateData),
  });
}

/**
 * List email templates
 */
export async function listEmailTemplates(templateType = null, isActive = null) {
  const params = new URLSearchParams();
  if (templateType) params.append('template_type', templateType);
  if (isActive !== null) params.append('is_active', isActive);

  const queryString = params.toString();
  const url = `/admin/email-templates${queryString ? `?${queryString}` : ''}`;
  return apiRequest(url);
}

/**
 * Delete multiple tickets (soft delete - move to trash)
 * Only closed tickets can be deleted
 */
export async function deleteTickets(ticketIds) {
  return apiRequest('/admin/tickets/delete', {
    method: 'POST',
    body: JSON.stringify({ ticket_ids: ticketIds }),
  });
}

/**
 * Get trash tickets (deleted tickets)
 */
export async function getTrashTickets(page = 1, pageSize = 10) {
  const params = new URLSearchParams();
  params.append('page', page);
  params.append('page_size', pageSize);

  const url = `/admin/tickets/trash?${params.toString()}`;
  return apiRequest(url);
}

/**
 * Restore tickets from trash
 */
export async function restoreTickets(ticketIds) {
  return apiRequest('/admin/tickets/restore', {
    method: 'POST',
    body: JSON.stringify({ ticket_ids: ticketIds }),
  });
}

/**
 * Permanently delete tickets from trash
 */
export async function permanentlyDeleteTickets(ticketIds) {
  const params = new URLSearchParams();
  ticketIds.forEach(id => params.append('ticket_ids', id));

  const url = `/admin/tickets/trash?${params.toString()}`;
  return apiRequest(url, {
    method: 'DELETE',
  });
}

// ---------------------------
// 🏢 ORGANIZATION ENDPOINTS
// ---------------------------

/**
 * Create a new organization (super admin only)
 */
export async function createOrganization(orgData) {
  return apiRequest('/admin/organizations', {
    method: 'POST',
    body: JSON.stringify(orgData),
  });
}

/**
 * List all organizations (super admin only)
 */
export async function listOrganizations() {
  return apiRequest('/admin/organizations');
}

/**
 * Invite a member to an organization (super admin only)
 */
export async function inviteMember(organizationId, memberData) {
  return apiRequest(`/admin/organizations/${organizationId}/invite`, {
    method: 'POST',
    body: JSON.stringify(memberData),
  });
}

/**
 * List organization members (super admin only)
 */
export async function listOrganizationMembers(organizationId) {
  return apiRequest(`/admin/organizations/${organizationId}/members`);
}

/**
 * Remove a member from an organization (super admin only)
 */
export async function removeMember(organizationId, memberId) {
  return apiRequest(`/admin/organizations/${organizationId}/members/${memberId}`, {
    method: 'DELETE',
  });
}

// ---------------------------
// 🎯 ROUTING RULES ENDPOINTS
// ---------------------------

/**
 * Create a routing rule
 */
export async function createRoutingRule(ruleData) {
  return apiRequest('/admin/routing-rules', {
    method: 'POST',
    body: JSON.stringify(ruleData),
  });
}

/**
 * List routing rules
 */
export async function listRoutingRules() {
  return apiRequest('/admin/routing-rules');
}

/**
 * Delete a routing rule
 */
export async function deleteRoutingRule(ruleId) {
  return apiRequest(`/admin/routing-rules/${ruleId}`, {
    method: 'DELETE',
  });
}

// ---------------------------
// 🏷️ TAGS & CATEGORIES ENDPOINTS
// ---------------------------

/**
 * Create a tag
 */
export async function createTag(tagData) {
  return apiRequest('/admin/tags', {
    method: 'POST',
    body: JSON.stringify(tagData),
  });
}

/**
 * List tags
 */
export async function listTags() {
  return apiRequest('/admin/tags');
}

/**
 * Get tags for a ticket
 */
export async function getTicketTags(ticketId) {
  return apiRequest(`/ticket/${ticketId}/tags`);
}

/**
 * Add tags to a ticket
 */
export async function addTagsToTicket(ticketId, tagIds) {
  return apiRequest(`/ticket/${ticketId}/tags`, {
    method: 'POST',
    body: JSON.stringify({ tag_ids: tagIds }),
  });
}

/**
 * Remove a tag from a ticket
 */
export async function removeTagFromTicket(ticketId, tagId) {
  return apiRequest(`/ticket/${ticketId}/tags/${tagId}`, {
    method: 'DELETE',
  });
}

/**
 * Create a category
 */
export async function createCategory(categoryData) {
  return apiRequest('/admin/categories', {
    method: 'POST',
    body: JSON.stringify(categoryData),
  });
}

/**
 * List categories
 */
export async function listCategories() {
  return apiRequest('/admin/categories');
}

/**
 * Set category for a ticket
 */
export async function setTicketCategory(ticketId, category) {
  return apiRequest(`/ticket/${ticketId}/category`, {
    method: 'PUT',
    body: JSON.stringify({ category }),
  });
}

/**
 * Update a tag
 */
export async function updateTag(tagId, tagData) {
  return apiRequest(`/admin/tags/${tagId}`, {
    method: 'PUT',
    body: JSON.stringify(tagData),
  });
}

/**
 * Delete a tag
 */
export async function deleteTag(tagId) {
  return apiRequest(`/admin/tags/${tagId}`, {
    method: 'DELETE',
  });
}

/**
 * Update a category
 */
export async function updateCategory(categoryId, categoryData) {
  return apiRequest(`/admin/categories/${categoryId}`, {
    method: 'PUT',
    body: JSON.stringify(categoryData),
  });
}

/**
 * Delete a category
 */
export async function deleteCategory(categoryId) {
  return apiRequest(`/admin/categories/${categoryId}`, {
    method: 'DELETE',
  });
}

