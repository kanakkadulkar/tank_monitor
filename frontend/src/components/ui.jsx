// src/components/ui.js  —  shared primitives

import React from 'react';

/* ── Card ─────────────────────────────────────────────────────────────────── */
export function Card({ children, style, accent }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: `1px solid ${accent ? 'var(--border2)' : 'var(--border)'}`,
      borderRadius: 12,
      padding: '1.25rem',
      ...style,
    }}>
      {children}
    </div>
  );
}

/* ── Stat ─────────────────────────────────────────────────────────────────── */
export function Stat({ label, value, unit, color, mono }) {
  return (
    <div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.65rem', letterSpacing: '.12em',
                    textTransform: 'uppercase', color: 'var(--muted)', marginBottom: '.3rem' }}>
        {label}
      </div>
      <div style={{
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-display)',
        fontSize: mono ? '1.6rem' : '2.4rem',
        fontWeight: mono ? 400 : undefined,
        lineHeight: 1,
        color: color || 'var(--text)',
      }}>
        {value}
        {unit && <span style={{ fontSize: '1rem', color: 'var(--muted)', marginLeft: '.25rem' }}>{unit}</span>}
      </div>
    </div>
  );
}

/* ── SectionTitle ─────────────────────────────────────────────────────────── */
export function SectionTitle({ children }) {
  return (
    <div style={{
      fontFamily: 'var(--font-display)',
      fontSize: '1.1rem',
      letterSpacing: '.1em',
      color: 'var(--muted)',
      marginBottom: '1rem',
      borderBottom: '1px solid var(--border)',
      paddingBottom: '.5rem',
    }}>
      {children}
    </div>
  );
}

/* ── Badge ────────────────────────────────────────────────────────────────── */
export function Badge({ children, type = 'info' }) {
  const colors = {
    info:     { bg: 'var(--cyan-dim)',  border: 'var(--cyan)',  text: 'var(--cyan)' },
    warning:  { bg: 'var(--amber-dim)', border: 'var(--amber)', text: 'var(--amber)' },
    danger:   { bg: 'var(--red-dim)',   border: 'var(--red)',   text: 'var(--red)' },
    success:  { bg: 'var(--green-dim)', border: 'var(--green)', text: 'var(--green)' },
  };
  const c = colors[type] || colors.info;
  return (
    <span style={{
      background: c.bg,
      border: `1px solid ${c.border}`,
      color: c.text,
      borderRadius: 6,
      padding: '.2rem .6rem',
      fontFamily: 'var(--font-mono)',
      fontSize: '.7rem',
      letterSpacing: '.08em',
      display: 'inline-block',
    }}>
      {children}
    </span>
  );
}

/* ── Spinner ──────────────────────────────────────────────────────────────── */
export function Spinner() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
      <div style={{
        width: 36, height: 36, borderRadius: '50%',
        border: '2px solid var(--border)',
        borderTopColor: 'var(--cyan)',
        animation: 'spin .8s linear infinite',
      }} />
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
