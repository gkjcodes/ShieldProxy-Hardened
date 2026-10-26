import { useState, useEffect } from 'react';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { BarChart3 } from 'lucide-react';
import { getVolumeData } from '../services/api';
import { generateMockStats } from '../data/mockData';
import './Analytics.css';

const TIME_RANGES = ['1H', '6H', '24H', '7D'];
const HOURS_MAP = { '1H': 1, '6H': 6, '24H': 24, '7D': 168 };

const THREAT_COLORS = {
  PROMPT_INJECTION: '#ef4444',
  JAILBREAK: '#f97316',
  SYSTEM_PROMPT_LEAK: '#f59e0b',
  SOCIAL_ENGINEERING: '#8b5cf6',
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

function generateTrendData(hours) {
  const data = [];
  const now = new Date();
  const points = Math.min(hours, 48);
  const interval = hours / points;

  for (let i = 0; i < points; i++) {
    const t = new Date(now.getTime() - (points - i) * interval * 3600000);
    const noise = () => Math.floor(Math.random() * 10);
    data.push({
      time: t.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
      'Prompt Injection': Math.floor(Math.sin(i / 3) * 8 + 15 + noise()),
      'Jailbreak': Math.floor(Math.cos(i / 4) * 5 + 8 + noise() * 0.6),
      'System Leak': Math.floor(Math.sin(i / 5 + 1) * 3 + 5 + noise() * 0.4),
      'Social Eng.': Math.floor(Math.cos(i / 6 + 2) * 2 + 3 + noise() * 0.3),
    });
  }
  return data;
}

function generateBlockRateData(hours) {
  const data = [];
  const points = Math.min(hours, 48);
  for (let i = 0; i < points; i++) {
    const base = 18 + Math.sin(i / 4) * 6;
    data.push({
      time: `${i}h`,
      rate: Math.round(base + Math.random() * 4),
    });
  }
  return data;
}

function generateTopClients() {
  const clients = [
    { name: 'client-theta-008', blocked: 342 },
    { name: 'client-beta-002', blocked: 287 },
    { name: 'demo-client-001', blocked: 198 },
    { name: 'client-gamma-003', blocked: 156 },
    { name: 'client-alpha-001', blocked: 89 },
  ];
  return clients;
}

// Simple geography mock
const GEO_DATA = [
  { country: 'USA', attacks: 342, x: 22, y: 40 },
  { country: 'Germany', attacks: 187, x: 50, y: 32 },
  { country: 'China', attacks: 256, x: 76, y: 40 },
  { country: 'Russia', attacks: 198, x: 62, y: 28 },
  { country: 'India', attacks: 145, x: 70, y: 48 },
  { country: 'Brazil', attacks: 112, x: 32, y: 62 },
];

export default function Analytics() {
  const [timeRange, setTimeRange] = useState('24H');
  const [trendData, setTrendData] = useState([]);
  const [blockRateData, setBlockRateData] = useState([]);
  const [hoveredGeo, setHoveredGeo] = useState(null);

  const topClients = generateTopClients();
  const maxBlocked = Math.max(...topClients.map(c => c.blocked));

  useEffect(() => {
    const hours = HOURS_MAP[timeRange];
    setTrendData(generateTrendData(hours));
    setBlockRateData(generateBlockRateData(hours));
  }, [timeRange]);

  return (
    <div className="analytics animate-fade-in">
      {/* Header */}
      <div className="page-header">
        <h1>
          <BarChart3 size={24} style={{ color: 'var(--neon-purple)' }} />
          Analytics
        </h1>
        <div className="tab-switcher">
          {TIME_RANGES.map(range => (
            <button
              key={range}
              className={timeRange === range ? 'active' : ''}
              onClick={() => setTimeRange(range)}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Section 1: Attack Trends */}
      <div className="glass-card analytics__chart-card" style={{ marginBottom: 20 }}>
        <h3 className="analytics__chart-title">Attack Trends</h3>
        <p className="analytics__chart-subtitle">Threat types over {timeRange}</p>
        <div style={{ width: '100%', height: 300 }}>
          <ResponsiveContainer>
            <LineChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="time" stroke="#475569" fontSize={10} tickLine={false} />
              <YAxis stroke="#475569" fontSize={10} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Line type="monotone" dataKey="Prompt Injection" stroke={THREAT_COLORS.PROMPT_INJECTION} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="Jailbreak" stroke={THREAT_COLORS.JAILBREAK} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="System Leak" stroke={THREAT_COLORS.SYSTEM_PROMPT_LEAK} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="Social Eng." stroke={THREAT_COLORS.SOCIAL_ENGINEERING} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="analytics__legend">
          {Object.entries(THREAT_COLORS).map(([type, color]) => (
            <div key={type} className="analytics__legend-item">
              <span className="analytics__legend-dot" style={{ background: color }}></span>
              <span>{type.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Section 2: Top Attacked Clients + Block Rate */}
      <div className="chart-grid chart-grid-2" style={{ marginBottom: 20 }}>
        {/* Top Attacked Clients */}
        <div className="glass-card analytics__chart-card">
          <h3 className="analytics__chart-title">Top Attacked Clients</h3>
          <p className="analytics__chart-subtitle">By block count</p>
          <div className="analytics__horizontal-bars">
            {topClients.map((c, i) => (
              <div key={c.name} className="analytics__h-bar animate-slide-in" style={{ animationDelay: `${i * 0.05}s` }}>
                <span className="analytics__h-bar-name">{c.name}</span>
                <div className="analytics__h-bar-track">
                  <div
                    className="analytics__h-bar-fill"
                    style={{
                      width: `${(c.blocked / maxBlocked) * 100}%`,
                      background: `linear-gradient(90deg, var(--neon-red), var(--neon-orange))`,
                    }}
                  ></div>
                </div>
                <span className="analytics__h-bar-value">{c.blocked}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Block Rate Over Time */}
        <div className="glass-card analytics__chart-card">
          <h3 className="analytics__chart-title">Block Rate Over Time</h3>
          <p className="analytics__chart-subtitle">Percentage blocked — threshold 20%</p>
          <div style={{ width: '100%', height: 240 }}>
            <ResponsiveContainer>
              <AreaChart data={blockRateData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradRate" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="time" stroke="#475569" fontSize={10} tickLine={false} />
                <YAxis stroke="#475569" fontSize={10} tickLine={false} unit="%" />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={20} stroke="var(--neon-red)" strokeDasharray="6 3" label={{ value: '20% threshold', fill: '#ef4444', fontSize: 10 }} />
                <Area type="monotone" dataKey="rate" name="Block Rate" stroke="#8b5cf6" fillOpacity={1} fill="url(#gradRate)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Section 3: Geography Simulation */}
      <div className="glass-card analytics__chart-card">
        <h3 className="analytics__chart-title">Geography Simulation</h3>
        <p className="analytics__chart-subtitle">Attack origin heatmap (simulated)</p>
        <div className="analytics__geo-map">
          {/* Simplified world map outline */}
          <svg viewBox="0 0 100 70" className="analytics__geo-svg">
            {/* Simple continent shapes */}
            <path d="M15,25 Q20,20 30,22 L35,28 Q30,38 25,40 L18,38 Q12,32 15,25Z" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
            <path d="M25,42 Q30,40 35,45 L32,60 Q28,65 24,58 L22,48 Q23,44 25,42Z" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
            <path d="M42,22 Q55,18 62,22 L65,30 Q60,38 52,36 L45,32 Q40,28 42,22Z" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
            <path d="M50,38 Q55,36 58,40 L56,50 Q52,52 48,48 L48,42 Q49,39 50,38Z" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
            <path d="M62,25 Q72,20 82,28 L85,38 Q80,50 72,48 L65,42 Q60,35 62,25Z" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
            <path d="M82,50 Q88,48 92,52 L90,60 Q86,62 82,58 L80,54 Q80,51 82,50Z" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />

            {/* Attack dots */}
            {GEO_DATA.map((g, i) => (
              <g key={i}>
                {/* Pulse ring */}
                <circle cx={g.x} cy={g.y} r={Math.sqrt(g.attacks) / 5 + 1} fill="none" stroke="var(--neon-red)" strokeWidth="0.3" opacity="0.5">
                  <animate attributeName="r" from={Math.sqrt(g.attacks) / 5} to={Math.sqrt(g.attacks) / 3 + 3} dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" from="0.5" to="0" dur="2s" repeatCount="indefinite" />
                </circle>
                {/* Core dot */}
                <circle
                  cx={g.x}
                  cy={g.y}
                  r={Math.sqrt(g.attacks) / 6 + 0.8}
                  fill="var(--neon-red)"
                  opacity="0.8"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHoveredGeo(g)}
                  onMouseLeave={() => setHoveredGeo(null)}
                />
              </g>
            ))}
          </svg>

          {/* Tooltip */}
          {hoveredGeo && (
            <div className="analytics__geo-tooltip" style={{ left: `${hoveredGeo.x}%`, top: `${hoveredGeo.y - 8}%` }}>
              <strong>{hoveredGeo.country}</strong>
              <span>{hoveredGeo.attacks} attacks</span>
            </div>
          )}

          {/* Legend */}
          <div className="analytics__geo-legend">
            {GEO_DATA.map(g => (
              <div key={g.country} className="analytics__geo-legend-item">
                <span className="analytics__geo-legend-dot"></span>
                <span>{g.country}</span>
                <strong>{g.attacks}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
