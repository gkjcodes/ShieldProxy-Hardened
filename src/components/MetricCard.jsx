export default function MetricCard({ title, value, subtitle, icon: Icon, color = 'var(--neon-purple)', trend }) {
  const dimColor = color.replace(')', ', 0.15)').replace('var(', '').replace('rgb(', 'rgba(');
  const bgColor = color.includes('--neon-')
    ? `var(${color.match(/--neon-\w+/)?.[0]}-dim)`
    : 'rgba(139, 92, 246, 0.15)';

  return (
    <div className="glass-card" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ flex: 1 }}>
          <p style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '1px',
            color: 'var(--text-secondary)',
            marginBottom: 8,
          }}>
            {title}
          </p>
          <p style={{
            fontSize: '2rem',
            fontWeight: 800,
            color: color,
            lineHeight: 1.1,
            textShadow: `0 0 20px ${color}40`,
            fontFamily: 'var(--font-mono)',
          }}>
            {value}
          </p>
          {subtitle && (
            <p style={{
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
              marginTop: 4,
            }}>
              {subtitle}
            </p>
          )}
          {trend && (
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              marginTop: 8,
              padding: '2px 8px',
              borderRadius: 999,
              fontSize: '0.7rem',
              fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              background: trend.direction === 'up' ? 'var(--neon-green-dim)' : 'var(--neon-red-dim)',
              color: trend.direction === 'up' ? 'var(--neon-green)' : 'var(--neon-red)',
              border: `1px solid ${trend.direction === 'up' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
            }}>
              {trend.direction === 'up' ? '↑' : '↓'} {trend.value}
            </div>
          )}
        </div>
        {Icon && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 44,
            height: 44,
            borderRadius: 'var(--radius-md)',
            background: bgColor,
            color: color,
            boxShadow: `0 0 16px ${color}30`,
            flexShrink: 0,
          }}>
            <Icon size={22} />
          </div>
        )}
      </div>
    </div>
  );
}
