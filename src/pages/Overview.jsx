import { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { BarChart3, ShieldOff, Shield, Zap } from 'lucide-react';
import MetricCard from '../components/MetricCard';
import ThreatBadge from '../components/ThreatBadge';
import { getDashboardStats, getVolumeData, getAlerts } from '../services/api';
import { generateMockThreatDistribution, generateMockPipelineLatency } from '../data/mockData';
import './Overview.css';

const CHART_COLORS = {
  blocked: '#ef4444',
  passed: '#10b981',
  purple: '#8b5cf6',
};

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip__label">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, fontSize: '0.75rem' }}>
          {p.name}: <strong>{p.value?.toLocaleString()}</strong>
        </p>
      ))}
    </div>
  );
}

export default function Overview() {
  const [stats, setStats] = useState(null);
  const [volume, setVolume] = useState([]);
  const [recentThreats, setRecentThreats] = useState([]);
  const threatDist = generateMockThreatDistribution();
  const pipelineLatency = generateMockPipelineLatency();

  useEffect(() => {
    const fetchData = async () => {
      const [s, v, a] = await Promise.all([getDashboardStats(), getVolumeData(24), getAlerts()]);
      setStats(s);
      setVolume(v);
      setRecentThreats((a || []).filter(t => t.threat_type !== 'SAFE').slice(0, 5));
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!stats) {
    return <div className="overview-loading"><div className="spinner"></div><p>Initializing Dashboard...</p></div>;
  }

  return (
    <div className="overview animate-fade-in">
      {/* Page Header */}
      <div className="page-header">
        <h1>
          <Shield size={24} style={{ color: 'var(--neon-purple)' }} />
          Overview
        </h1>
        <div className="page-header__live-badge">
          <span className="status-dot active"></span>
          LIVE
        </div>
      </div>

      {/* Metric Cards */}
      <div className="metric-grid">
        <MetricCard
          title="Total Requests"
          value={stats.total_requests?.toLocaleString()}
          subtitle="Today"
          icon={BarChart3}
          color="var(--neon-blue)"
          trend={{ direction: 'up', value: '+12.4%' }}
        />
        <MetricCard
          title="Threats Blocked"
          value={stats.total_blocked?.toLocaleString()}
          subtitle="Intercepted"
          icon={ShieldOff}
          color="var(--neon-red)"
          trend={{ direction: 'up', value: '+8.2%' }}
        />
        <MetricCard
          title="Block Rate"
          value={`${stats.block_rate}%`}
          subtitle="Detection accuracy"
          icon={Shield}
          color="var(--neon-orange)"
        />
        <MetricCard
          title="Avg Latency"
          value={`${stats.avg_latency_ms}ms`}
          subtitle="Pipeline overhead"
          icon={Zap}
          color="var(--neon-green)"
          trend={{ direction: 'down', value: '-3.1ms' }}
        />
      </div>

      {/* Row 2: Traffic Volume + Threat Distribution */}
      <div className="chart-grid chart-grid-60-40">
        {/* Traffic Volume */}
        <div className="glass-card overview__chart-card">
          <h3 className="overview__chart-title">Traffic Volume</h3>
          <p className="overview__chart-subtitle">Last 24 hours — Blocked vs Passed</p>
          <div style={{ width: '100%', height: 260 }}>
            <ResponsiveContainer>
              <AreaChart data={volume} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradBlocked" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={CHART_COLORS.blocked} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={CHART_COLORS.blocked} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradPassed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={CHART_COLORS.passed} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={CHART_COLORS.passed} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="timestamp" stroke="#475569" fontSize={10} tickLine={false} />
                <YAxis stroke="#475569" fontSize={10} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="passed" name="Passed" stroke={CHART_COLORS.passed} fillOpacity={1} fill="url(#gradPassed)" strokeWidth={2} />
                <Area type="monotone" dataKey="blocked" name="Blocked" stroke={CHART_COLORS.blocked} fillOpacity={1} fill="url(#gradBlocked)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Threat Distribution */}
        <div className="glass-card overview__chart-card">
          <h3 className="overview__chart-title">Threat Distribution</h3>
          <p className="overview__chart-subtitle">Attack type breakdown</p>
          <div style={{ width: '100%', height: 200 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={threatDist} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4} dataKey="value">
                  {threatDist.map((entry, i) => (
                    <Cell key={i} fill={entry.color} stroke="transparent" />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="overview__pie-legend">
            {threatDist.map((d, i) => (
              <div key={i} className="overview__pie-legend-item">
                <span className="overview__pie-legend-dot" style={{ background: d.color }}></span>
                <span>{d.name}</span>
                <strong>{d.value}%</strong>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Row 3: Pipeline Latency + Recent Threats */}
      <div className="chart-grid chart-grid-2">
        {/* Pipeline Latency */}
        <div className="glass-card overview__chart-card">
          <h3 className="overview__chart-title">Pipeline Latency</h3>
          <p className="overview__chart-subtitle">Average per stage (ms)</p>
          <div style={{ width: '100%', height: 240 }}>
            <ResponsiveContainer>
              <BarChart data={pipelineLatency} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="stage" stroke="#475569" fontSize={9} tickLine={false} angle={-20} textAnchor="end" height={50} />
                <YAxis stroke="#475569" fontSize={10} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="latency" name="Latency (ms)" radius={[4, 4, 0, 0]}>
                  {pipelineLatency.map((entry, i) => (
                    <Cell key={i} fill={entry.color} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Threats */}
        <div className="glass-card overview__chart-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 className="overview__chart-title" style={{ margin: 0 }}>Recent Threats</h3>
            <div className="page-header__live-badge">
              <span className="status-dot active"></span>
              LIVE
            </div>
          </div>
          <div className="overview__threats-table">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Client</th>
                  <th>Type</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {recentThreats.length === 0 ? (
                  <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 30 }}>No threats detected</td></tr>
                ) : recentThreats.map((t, i) => (
                  <tr key={t.id || i} className="animate-slide-in" style={{ animationDelay: `${i * 0.05}s` }}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                      {new Date(t.timestamp).toLocaleTimeString()}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                      {t.client_id?.split('-').slice(0, 2).join('-')}
                    </td>
                    <td><ThreatBadge type={t.threat_type} /></td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: t.confidence > 0.8 ? 'var(--neon-red)' : 'var(--neon-yellow)' }}>
                      {(t.confidence * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
