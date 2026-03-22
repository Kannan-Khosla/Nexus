/**
 * Authentication service for user login, registration, and token management
 */

const DEFAULT_BASE_URL = '';

/**
 * Get base URL from localStorage or use default
 */
function getBaseUrl() {
  return localStorage.getItem('baseUrl') || DEFAULT_BASE_URL;
}

/**
 * Get JWT token from localStorage
 */
export function getToken() {
  return localStorage.getItem('token') || null;
}

/**
 * Set JWT token
 */
export function setToken(token) {
  if (token) {
    localStorage.setItem('token', token);
  } else {
    localStorage.removeItem('token');
  }
}

/**
 * Get user data from localStorage
 */
export function getUser() {
  const userStr = localStorage.getItem('user');
  return userStr ? JSON.parse(userStr) : null;
}

/**
 * Set user data
 */
export function setUser(user) {
  if (user) {
    localStorage.setItem('user', JSON.stringify(user));
  } else {
    localStorage.removeItem('user');
  }
}

/**
 * Clear auth data
 */
export function clearAuth() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
}

/**
 * Make authenticated API request
 */
async function authRequest(url, options = {}) {
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
      // Handle 401 Unauthorized - clear auth and redirect
      if (response.status === 401) {
        clearAuth();
        throw new Error('Session expired. Please login again.');
      }
      throw new Error(data.detail || data.error || `HTTP ${response.status}`);
    }
    
    return { data, error: null };
  } catch (error) {
    return { data: null, error: error.message || 'Request failed' };
  }
}

/**
 * Register a new customer
 */
export async function register(email, password, name) {
  const { data, error } = await authRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, name }),
  });
  
  if (!error && data) {
    setToken(data.access_token);
    setUser(data.user);
  }
  
  return { data, error };
}

/**
 * Login user
 */
export async function login(email, password) {
  const { data, error } = await authRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  
  if (!error && data) {
    setToken(data.access_token);
    setUser(data.user);
  }
  
  return { data, error };
}

/**
 * Logout user
 */
export function logout() {
  clearAuth();
}

/**
 * Get current user info
 */
export async function getCurrentUser() {
  return authRequest('/auth/me');
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated() {
  return getToken() !== null && getUser() !== null;
}

/**
 * Get user role
 */
export function getUserRole() {
  const user = getUser();
  return user ? user.role : null;
}

