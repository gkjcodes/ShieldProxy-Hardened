import { useState, useEffect, useRef } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import ThreatBadge from '../components/ThreatBadge';
import { getAlerts } from '../services/api';
import './Alerts.css';

const ANOMALIES = [
  { id: 'a1', severity: 'critical', color: 'var(--neon-red)', title: 'Spike detected: 47 injection attempts in 2 min', time: '2 min ago' },
  { id: 'a2', severity: 'warning', color: 'var(--neon-yellow)', title: 'New client fingerprint: unusual UA string detected', time: '8 min ago' },
  { id: 'a3', severity: 'high', color: 'var(--neon-orange)', title: 'Output filter triggered: possible prompt leak in response', time: '14 min ago' },
  { id: 'a4', severity: 'critical', color: 'var(--neon-red)', title: 'Rate limit hit 8x by client-theta-008 in 30 sec', time: '22 min ago' },
];

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [anomalies, setAnomalies] = useState(ANOMALIES);
  const feedRef = useRef(null);

  useEffect(() => {
    const fetch = async () => {
      const data = await getAlerts();
      setAlerts(data || []);
    };
    fetch();
    const interval = setInterval(fetch, 3000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll to top on new alerts
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = 0;
    }
  }, [alerts.length]);

  const dismissAnomaly = (id) => {
    setAnomalies(prev => prev.filter(a => a.id !== id));
  };

  return (
    <div className="alerts animate-fade-in">
      {/* Page Header */}
      <div className="page-header">
        <h1>
          <AlertTriangle size={24} style={{ color: 'var(--neon-orange)' }} />
          Alerts Center
        </h1>
        <div className="page-header__live-badge">
          <span className="status-dot active"></span>
          LIVE · {alerts.length} events
        </div>
      </div>

      <div className="alerts__grid">
        {/* LEFT: Live Threat Feed */}
        <div className="alerts__feed">
          <h3 className="alerts__section-title">Live Threat Feed</h3>
          <div className="alerts__feed-list" ref={feedRef}>
            {alerts.length === 0 ? (
              <div className="alerts__empty">
                <AlertTriangle size={32} style={{ color: 'var(--text-muted)' }} />
                <p>No alerts detected</p>
              </div>
            ) : alerts.map((alert, i) => (
              <div
                key={alert.id || i}
                className="glass-card alerts__feed-item animate-slide-in"
                style={{
                  animationDelay: `${i * 0.03}s`,
                  borderLeftColor: alert.threat_type === 'PROMPT_INJECTION' ? 'var(--neon-red)'
                    : alert.threat_type === 'JAILBREAK' ? 'var(--neon-orange)'
                    : alert.threat_type === 'SYSTEM_PROMPT_LEAK' ? 'var(--neon-yellow)'
                    : 'var(--neon-purple)',
                }}
              >
                <div className="alerts__feed-item-header">
                  <span className="alerts__feed-time">
                    {new Date(alert.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="alerts__feed-client">{alert.client_id}</span>
                </div>
                <div className="alerts__feed-item-body">
                  <div className="alerts__feed-item-badges">
                    <ThreatBadge type={alert.threat_type} />
                    <span className="alerts__feed-confidence" style={{
                      color: alert.confidence > 0.8 ? 'var(--neon-red)' : 'var(--neon-yellow)',
                    }}>
                      {(alert.confidence * 100).toFixed(0)}%
                    </span>
                    <span className={`badge ${alert.is_blocked ? 'badge-blocked' : 'badge-passed'}`}>
                      {alert.is_blocked ? 'BLOCKED' : 'PASSED'}
                    </span>
                  </div>
                  {alert.prompt_preview && (
                    <p className="alerts__feed-prompt">{alert.prompt_preview}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT: Critical Anomalies */}
        <div className="alerts__anomalies">
          <h3 className="alerts__section-title">Critical Anomalies</h3>
          <div className="alerts__anomalies-list">
            {anomalies.length === 0 ? (
              <div className="alerts__empty" style={{ padding: 30 }}>
                <p style={{ color: 'var(--neon-green)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>All clear — no anomalies</p>
              </div>
            ) : anomalies.map((a) => (
              <div
                key={a.id}
                className="glass-card alerts__anomaly-card"
                style={{ borderLeftColor: a.color }}
              >
                <div className="alerts__anomaly-header">
                  <span className="alerts__anomaly-severity" style={{ color: a.color }}>
                    ● {a.severity.toUpperCase()}
                  </span>
                  <button
                    className="alerts__anomaly-dismiss"
                    onClick={() => dismissAnomaly(a.id)}
                    title="Dismiss"
                  >
                    <X size={14} />
                  </button>
                </div>
                <p className="alerts__anomaly-title">{a.title}</p>
                <span className="alerts__anomaly-time">{a.time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
