const THREAT_CONFIG = {
  PROMPT_INJECTION: { color: 'var(--neon-red)', bg: 'var(--neon-red-dim)', border: 'rgba(239, 68, 68, 0.3)', label: 'Injection' },
  JAILBREAK: { color: 'var(--neon-orange)', bg: 'rgba(249, 115, 22, 0.15)', border: 'rgba(249, 115, 22, 0.3)', label: 'Jailbreak' },
  SYSTEM_PROMPT_LEAK: { color: 'var(--neon-yellow)', bg: 'var(--neon-yellow-dim)', border: 'rgba(245, 158, 11, 0.3)', label: 'Sys Leak' },
  SOCIAL_ENGINEERING: { color: 'var(--neon-purple)', bg: 'var(--neon-purple-dim)', border: 'rgba(139, 92, 246, 0.3)', label: 'Social Eng' },
  SAFE: { color: 'var(--neon-green)', bg: 'var(--neon-green-dim)', border: 'rgba(16, 185, 129, 0.3)', label: 'Safe' },
  RATE_LIMIT: { color: 'var(--neon-blue)', bg: 'var(--neon-blue-dim)', border: 'rgba(59, 130, 246, 0.3)', label: 'Rate Limit' },
};

export default function ThreatBadge({ type }) {
  const config = THREAT_CONFIG[type] || THREAT_CONFIG.SAFE;

  return (
    <span
      className="badge"
      style={{
        background: config.bg,
        color: config.color,
        border: `1px solid ${config.border}`,
      }}
    >
      {config.label}
    </span>
  );
}
