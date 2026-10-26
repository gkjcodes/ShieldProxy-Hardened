const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Fallback mock data generators ──
import {
  generateMockStats,
  generateMockAlerts,
  generateMockClients,
  generateMockVolume,
  generateMockSimulatorResponse,
} from '../data/mockData';

export const analyzePrompt = async ({ message, clientId, firewallEnabled }) => {
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

  try {
    const res = await fetch(`${BASE_URL}/v1/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, client_id: clientId || 'demo-client-001' }),
    });

    if (res.status === 403 || res.status === 429) {
      const data = await res.json();
      // FastAPI wraps HTTPException in { detail: {...} }
      return data.detail || data;
    }

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('API unavailable, using mock:', err.message);
    return generateMockSimulatorResponse(message);
  }
};

export const getDashboardStats = async () => {
  try {
    const res = await fetch(`${BASE_URL}/v1/dashboard/stats`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return generateMockStats();
  }
};

export const getAlerts = async () => {
  try {
    const res = await fetch(`${BASE_URL}/v1/dashboard/alerts`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return generateMockAlerts(50);
  }
};

export const getClients = async () => {
  try {
    const res = await fetch(`${BASE_URL}/v1/dashboard/clients`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return generateMockClients(10);
  }
};

export const getVolumeData = async (hours = 24) => {
  try {
    const res = await fetch(`${BASE_URL}/v1/dashboard/volume?hours=${hours}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return generateMockVolume(hours);
  }
};
