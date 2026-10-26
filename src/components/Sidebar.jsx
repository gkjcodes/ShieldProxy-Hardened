import { useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  AlertTriangle,
  BarChart3,
  FlaskConical,
  Settings,
  ChevronLeft,
  ChevronRight,
  Shield,
} from 'lucide-react';
import './Sidebar.css';

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: 'Overview', path: '/' },
  { icon: Users, label: 'Clients', path: '/clients' },
  { icon: AlertTriangle, label: 'Alerts', path: '/alerts' },
  { icon: BarChart3, label: 'Analytics', path: '/analytics' },
  { icon: FlaskConical, label: 'Simulator', path: '/simulator' },
  { icon: Settings, label: 'Settings', path: '/settings' },
];

export default function Sidebar({ collapsed, onToggle }) {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <aside className={`sidebar ${collapsed ? 'sidebar--collapsed' : ''}`}>
      {/* Logo */}
      <div className="sidebar__logo" onClick={() => navigate('/')}>
        <Shield size={collapsed ? 28 : 24} className="sidebar__logo-icon" />
        {!collapsed && <span className="sidebar__logo-text">ShieldProxy</span>}
      </div>

      {/* Navigation */}
      <nav className="sidebar__nav">
        {NAV_ITEMS.map(({ icon: Icon, label, path }) => {
          const isActive = location.pathname === path;
          return (
            <button
              key={path}
              className={`sidebar__nav-item ${isActive ? 'sidebar__nav-item--active' : ''}`}
              onClick={() => navigate(path)}
              title={collapsed ? label : undefined}
            >
              <Icon size={20} />
              {!collapsed && <span>{label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="sidebar__footer">
        {/* Firewall Status */}
        <div className="sidebar__status">
          <span className="sidebar__status-dot"></span>
          {!collapsed && <span className="sidebar__status-text">FIREWALL ACTIVE</span>}
        </div>

        {/* Collapse Toggle */}
        <button className="sidebar__toggle" onClick={onToggle} title={collapsed ? 'Expand' : 'Collapse'}>
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>
    </aside>
  );
}
