import { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import AnimatedBackground from './components/AnimatedBackground';
import CustomCursor from './components/CustomCursor';
import Overview from './pages/Overview';
import Clients from './pages/Clients';
import Alerts from './pages/Alerts';
import Analytics from './pages/Analytics';
import Simulator from './pages/Simulator';

function DashboardLayout({ children }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="wave-bg" style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* Animated Background */}
      <AnimatedBackground />

      {/* Floating Orbs */}
      <div className="floating-orb orb-1"></div>
      <div className="floating-orb orb-2"></div>
      <div className="floating-orb orb-3"></div>

      {/* Particle Field */}
      <div className="particle-field">
        {[...Array(15)].map((_, i) => (
          <div
            key={i}
            className="particle"
            style={{
              left: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 5}s`,
              animationDuration: `${Math.random() * 10 + 10}s`,
            }}
          ></div>
        ))}
      </div>

      {/* Custom Cursor */}
      <CustomCursor />

      {/* Sidebar */}
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />

      {/* Main Content */}
      <main className={`main-content ${sidebarCollapsed ? 'collapsed' : ''}`}>
        {children}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <DashboardLayout>
            <Overview />
          </DashboardLayout>
        }
      />
      <Route
        path="/clients"
        element={
          <DashboardLayout>
            <Clients />
          </DashboardLayout>
        }
      />
      <Route
        path="/alerts"
        element={
          <DashboardLayout>
            <Alerts />
          </DashboardLayout>
        }
      />
      <Route
        path="/analytics"
        element={
          <DashboardLayout>
            <Analytics />
          </DashboardLayout>
        }
      />
      <Route
        path="/simulator"
        element={
          <DashboardLayout>
            <Simulator />
          </DashboardLayout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
