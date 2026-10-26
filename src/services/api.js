const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function getHeaders(customHeaders = {}) {
  return {
    'Content-Type': 'application/json',
    ...customHeaders,
  };
}

// Fallback mock data generators
import {
  generateMockStats,
  generateMockAlerts,
  generateMockClients,
  generateMockVolume,
  generateMockSimulatorResponse,
} from '../data/mockData';

/**
 * Explicit browser authentication using server-validated credentials.
 * Establishes an HttpOnly, SameSite session cookie on success.
 */
export const login = async (apiKey) => {
  const res = await fetch(`${BASE_URL}/v1/auth/login`, {
    method: 'POST',
    credentials: 'include',
    headers: getHeaders(),
    body: JSON.stringify({ api_key: apiKey }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Authentication failed');
  }
  return await res.json();
};

/**
 * Revoke the current server-side session and clear the session cookie.
 */
export const logout = async () => {
  const res = await fetch(`${BASE_URL}/v1/auth/logout`, {
    method: 'POST',
    credentials: 'include',
    headers: getHeaders(),
  });
  return await res.json().catch(() => ({ status: 'logged_out' }));
};

/**
 * Query current session status without storing or disclosing credentials.
 */
export const getSession = async () => {
  try {
    const res = await fetch(`${BASE_URL}/v1/auth/session`, {
      credentials: 'include',
      headers: getHeaders(),
    });
    if (!res.ok) return { authenticated: false, tenant_id: null, role: null };
    return await res.json();
  } catch {
    return { authenticated: false, tenant_id: null, role: null };
  }
};

/**
 * Execute chat prompt analysis via hardened gateway.
 * Transmits session cookie via credentials: 'include'.
 */
export const analyzePrompt = async ({ message, clientId, firewallEnabled, apiKey = null }) => {
  if (!firewallEnabled) {
    return {
      request_id: crypto.randomUUID?.()?.slice(0, 16) || Math.random().toString(36).slice(2, 18),
      blocked: false,
      bypass: true,
      block_reason: null,
      threat_analysis: { threat_type: 'BYPASSED', confidence: 0, matched_patterns: [] },
      pii_scrubbed: false,
      pii_count: 0,
      response: 'I understand your question. Let me provide a thoughtful response. Based on my training, I can help you with a wide range of topics. Could you provide more specific details so I can give you the most helpful answer?',
      output_filtered: false,
      total_latency_ms: Math.floor(Math.random() * 300 + 100),
      pipeline_stages: [
        { stage: 'rate_limiter', passed: true, latency_ms: 0 },
        { stage: 'threat_classifier', passed: true, latency_ms: 0 },
        { stage: 'pii_scrubber', passed: true, latency_ms: 0 },
        { stage: 'audit_logger', passed: true, latency_ms: 0 },
        { stage: 'llm_gateway', passed: true, latency_ms: Math.floor(Math.random() * 300 + 100) },
        { stage: 'output_filter', passed: true, latency_ms: 0 },
      ],
    };
  }

  const customHeaders = {};
  if (apiKey) {
    customHeaders['X-API-Key'] = apiKey;
  }

  try {
    const res = await fetch(`${BASE_URL}/v1/chat`, {
      method: 'POST',
      credentials: 'include',
      headers: getHeaders(customHeaders),
      body: JSON.stringify({ message }),
    });

    if (res.status === 401 || res.status === 403 || res.status === 413 || res.status === 429) {
      const data = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      return data.detail || data;
    }

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('API unavailable or returned error, using fallback:', err.message);
    return generateMockSimulatorResponse(message);
  }
};

export const getDashboardStats = async () => {
  try {
    const res = await fetch(`${BASE_URL}/v1/dashboard/stats`, {
      credentials: 'include',
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return generateMockStats();
  }
};

export const getAlerts = async () => {
  try {
    const res = await fetch(`${BASE_URL}/v1/dashboard/alerts`, {
      credentials: 'include',
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return generateMockAlerts(50);
  }
};

export const getClients = async () => {
  try {
    const res = await fetch(`${BASE_URL}/v1/dashboard/clients`, {
      credentials: 'include',
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return generateMockClients(10);
  }
};

export const getVolumeData = async (hours = 24) => {
  try {
    const res = await fetch(`${BASE_URL}/v1/dashboard/volume?hours=${hours}`, {
      credentials: 'include',
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return generateMockVolume(hours);
  }
};