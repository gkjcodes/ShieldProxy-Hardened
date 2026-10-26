import { useEffect, useRef } from 'react';

export default function CustomCursor() {
  const outerRef = useRef(null);
  const innerRef = useRef(null);
  const pos = useRef({ x: 0, y: 0 });
  const outerPos = useRef({ x: 0, y: 0 });
  const isHovering = useRef(false);

  useEffect(() => {
    // Hide on touch devices
    if ('ontouchstart' in window) return;

    document.body.style.cursor = 'none';

    const handleMouseMove = (e) => {
      pos.current = { x: e.clientX, y: e.clientY };
      if (innerRef.current) {
        innerRef.current.style.left = `${e.clientX}px`;
        innerRef.current.style.top = `${e.clientY}px`;
      }
    };

    const handleMouseOver = (e) => {
      const el = e.target;
      const clickable =
        el.tagName === 'BUTTON' ||
        el.tagName === 'A' ||
        el.tagName === 'INPUT' ||
        el.tagName === 'TEXTAREA' ||
        el.tagName === 'SELECT' ||
        el.closest('button') ||
        el.closest('a') ||
        el.style?.cursor === 'pointer' ||
        window.getComputedStyle(el).cursor === 'pointer';

      isHovering.current = !!clickable;
    };

    // Lerp animation for outer ring
    let raf;
    const animate = () => {
      outerPos.current.x += (pos.current.x - outerPos.current.x) * 0.15;
      outerPos.current.y += (pos.current.y - outerPos.current.y) * 0.15;

      if (outerRef.current) {
        outerRef.current.style.left = `${outerPos.current.x}px`;
        outerRef.current.style.top = `${outerPos.current.y}px`;
        outerRef.current.style.transform = `translate(-50%, -50%) scale(${isHovering.current ? 2 : 1})`;
        outerRef.current.style.borderColor = isHovering.current
          ? 'var(--neon-green)'
          : 'var(--neon-purple)';
      }
      raf = requestAnimationFrame(animate);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseover', handleMouseOver);
    animate();

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseover', handleMouseOver);
      cancelAnimationFrame(raf);
      document.body.style.cursor = '';
    };
  }, []);

  // Don't render on touch devices
  if (typeof window !== 'undefined' && 'ontouchstart' in window) return null;

  return (
    <>
      <div
        ref={outerRef}
        style={{
          position: 'fixed',
          width: 24,
          height: 24,
          borderRadius: '50%',
          border: '1.5px solid var(--neon-purple)',
          pointerEvents: 'none',
          zIndex: 9999,
          transform: 'translate(-50%, -50%)',
          transition: 'border-color 0.3s ease, transform 0.3s ease',
          mixBlendMode: 'difference',
        }}
      />
      <div
        ref={innerRef}
        style={{
          position: 'fixed',
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: 'var(--neon-purple)',
          pointerEvents: 'none',
          zIndex: 9999,
          transform: 'translate(-50%, -50%)',
          boxShadow: '0 0 6px var(--neon-purple)',
        }}
      />
    </>
  );
}
