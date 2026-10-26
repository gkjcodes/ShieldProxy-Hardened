import { useState, useEffect } from 'react';
import { Users, Search } from 'lucide-react';
import { getClients } from '../services/api';
import './Clients.css';

export default function Clients() {
  const [clients, setClients] = useState([]);
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    const fetch = async () => {
      const data = await getClients();
      setClients(data || []);
    };
    fetch();
    const interval = setInterval(fetch, 10000);
    return () => clearInterval(interval);
  }, []);

  const filtered = clients.filter(c =>
    c.client_id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="clients animate-fade-in">
      {/* Page Header */}
      <div className="page-header">
        <h1>
          <Users size={24} style={{ color: 'var(--neon-purple)' }} />
          Connected Clients
          <span className="clients__count-badge">{clients.length}</span>
        </h1>
      </div>

      {/* Search */}
      <div className="clients__search">
        <div className="search-input">
          <Search size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <input
            type="text"
            placeholder="Search clients..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Table */}
      <div className="glass-card clients__table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Client ID</th>
              <th>API Key</th>
              <th>Requests</th>
              <th>Blocked</th>
              <th>Block Rate</th>
              <th>Last Active</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>
                  No clients found
                </td>
              </tr>
            ) : filtered.map((c, i) => (
              <>
                <tr
                  key={c.client_id}
                  className="clients__row animate-slide-in"
                  style={{ animationDelay: `${i * 0.03}s`, cursor: 'pointer' }}
                  onClick={() => setExpandedId(expandedId === c.client_id ? null : c.client_id)}
                >
                  <td>
                    <span className="clients__id">{c.client_id}</span>
                  </td>
                  <td>
                    <span className="clients__api-key">{c.api_key_masked}</span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>
                    {c.total_requests?.toLocaleString()}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--neon-red)' }}>
                    {c.total_blocked?.toLocaleString()}
                  </td>
                  <td>
                    <div className="clients__block-rate">
                      <span className="clients__block-rate-value" style={{
                        color: c.block_rate > 30 ? 'var(--neon-red)' : c.block_rate > 15 ? 'var(--neon-yellow)' : 'var(--neon-green)',
                      }}>
                        {c.block_rate}%
                      </span>
                      <div className="progress-bar">
                        <div
                          className="progress-bar-fill"
                          style={{
                            width: `${Math.min(c.block_rate, 100)}%`,
                            background: c.block_rate > 30 ? 'var(--neon-red)' : c.block_rate > 15 ? 'var(--neon-yellow)' : 'var(--neon-green)',
                          }}
                        ></div>
                      </div>
                    </div>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {c.last_active ? new Date(c.last_active).toLocaleTimeString() : '—'}
                  </td>
                  <td>
                    <div className="clients__status">
                      <span className={`status-dot ${c.status === 'active' ? 'active' : 'idle'}`}></span>
                      <span style={{ color: c.status === 'active' ? 'var(--neon-green)' : 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                        {c.status}
                      </span>
                    </div>
                  </td>
                </tr>
                {expandedId === c.client_id && (
                  <tr key={`${c.client_id}-expanded`} className="clients__expanded-row">
                    <td colSpan={7}>
                      <div className="clients__expanded">
                        <h4>Recent Activity — {c.client_id}</h4>
                        <div className="clients__expanded-stats">
                          <div className="clients__expanded-stat">
                            <span className="clients__expanded-stat-label">Pass Rate</span>
                            <span className="clients__expanded-stat-value" style={{ color: 'var(--neon-green)' }}>
                              {(100 - c.block_rate).toFixed(1)}%
                            </span>
                          </div>
                          <div className="clients__expanded-stat">
                            <span className="clients__expanded-stat-label">Passed</span>
                            <span className="clients__expanded-stat-value">
                              {(c.total_requests - c.total_blocked).toLocaleString()}
                            </span>
                          </div>
                          <div className="clients__expanded-stat">
                            <span className="clients__expanded-stat-label">Threat Risk</span>
                            <span className="clients__expanded-stat-value" style={{
                              color: c.block_rate > 30 ? 'var(--neon-red)' : c.block_rate > 15 ? 'var(--neon-yellow)' : 'var(--neon-green)',
                            }}>
                              {c.block_rate > 30 ? 'HIGH' : c.block_rate > 15 ? 'MEDIUM' : 'LOW'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
