import React, { useEffect, useState, useRef } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Card, Stat, SectionTitle, Badge, Spinner } from '../components/ui';
import { getBuffer, getHourly, getAnalysis, getLatest, getFlowSummary } from '../services/api';
import { format } from 'date-fns';

const TANK_H = 240;

/* ── Tank fill visualiser ─────────────────────────────────────────────────── */
function TankVisual({ pct }) {
  const h     = Math.max(0, Math.min(100, pct || 0));
  const color = h < 15 ? 'var(--red)' : h < 30 ? 'var(--amber)' : 'var(--cyan)';
  const glow  = h < 15 ? 'var(--red)' : h < 30 ? 'var(--amber)' : 'var(--cyan)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '.6rem' }}>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: '.65rem',
        letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--muted)',
      }}>
        Tank Level
      </div>

      {/* outer shell */}
      <div style={{
        position: 'relative', width: 72, height: 180,
        border: '2px solid var(--border2)',
        borderRadius: '6px 6px 10px 10px',
        overflow: 'hidden', background: 'var(--surface2)',
        boxShadow: `0 0 20px rgba(0,0,0,.6), inset 0 0 0 1px rgba(255,255,255,.04)`,
      }}>
        {/* fill */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          height: `${h}%`,
          background: `linear-gradient(180deg, ${color}66 0%, ${color}cc 100%)`,
          transition: 'height 1.2s cubic-bezier(.4,0,.2,1)',
          boxShadow: `0 -4px 20px ${glow}55`,
        }}>
          {/* animated wave */}
          <div style={{
            position: 'absolute', top: -4, left: 0, right: 0, height: 8,
            background: `linear-gradient(90deg, transparent, ${color}88, transparent)`,
            animation: 'wave 2s ease-in-out infinite',
          }} />
        </div>

        {/* tick marks */}
        {[25, 50, 75].map(t => (
          <div key={t} style={{
            position: 'absolute', bottom: `${t}%`, left: 0, right: 0,
            height: 1, background: 'rgba(255,255,255,0.06)',
            display: 'flex', alignItems: 'center',
          }}>
            <span style={{
              position: 'absolute', right: 4,
              fontFamily: 'var(--font-mono)', fontSize: '.55rem',
              color: 'rgba(255,255,255,0.2)', lineHeight: 1,
            }}>{t}</span>
          </div>
        ))}

        {/* pct label */}
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--font-display)', fontSize: '1.5rem',
          color: '#fff', textShadow: '0 1px 6px rgba(0,0,0,.9)',
          pointerEvents: 'none',
        }}>
          {h.toFixed(0)}%
        </div>
      </div>

      {/* bottom cap */}
      <div style={{
        width: 80, height: 6, borderRadius: '0 0 6px 6px',
        background: 'var(--border2)', marginTop: -8,
      }} />
    </div>
  );
}

/* ── State badge ──────────────────────────────────────────────────────────── */
function StateChip({ state }) {
  const map = {
    Filling:  { type: 'success', icon: '▼', label: 'Filling' },
    Emptying: { type: 'warning', icon: '▲', label: 'Emptying' },
    Stable:   { type: 'info',    icon: '●', label: 'Stable' },
  };
  const m = map[state] || map.Stable;
  return <Badge type={m.type}>{m.icon} {m.label}</Badge>;
}

/* ── Tier badge ──────────────────────────────────────────────────────────── */
function TierBadge({ tier }) {
  const map = {
    log:       { type: 'info',    label: 'LOG' },
    dashboard: { type: 'warning', label: 'DASHBOARD' },
    alert:     { type: 'warning', label: 'ALERT' },
    critical:  { type: 'danger',  label: 'CRITICAL' },
  };
  const m = map[tier] || map.log;
  return <Badge type={m.type}>{m.label}</Badge>;
}

/* ── Flow direction badge ────────────────────────────────────────────────── */
function FlowBadge({ direction }) {
  const map = {
    draining: { type: 'danger',  icon: '↓', label: 'Draining' },
    filling:  { type: 'success', icon: '↑', label: 'Filling' },
    stable:   { type: 'info',    icon: '→', label: 'Stable' },
  };
  const m = map[direction] || map.stable;
  return <Badge type={m.type}>{m.icon} {m.label}</Badge>;
}

/* ── Custom tooltip ───────────────────────────────────────────────────────── */
function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--surface2)', border: '1px solid var(--border2)',
      borderRadius: 8, padding: '.6rem .9rem',
      fontFamily: 'var(--font-mono)', fontSize: '.72rem',
    }}>
      <div style={{ color: 'var(--muted)', marginBottom: '.3rem' }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(2) : p.value}
        </div>
      ))}
    </div>
  );
}

/* ── Main Dashboard ───────────────────────────────────────────────────────── */
export default function Dashboard() {
  const [buffer,   setBuffer]  = useState([]);
  const [hourly,   setHourly]  = useState([]);
  const [analysis, setAna]     = useState(null);
  const [live,     setLive]    = useState(null);
  const [flow,     setFlow]    = useState(null);
  const [alerts,   setAlerts]  = useState([]);
  const timerRef = useRef(null);

  /* Poll buffer + hourly + latest + flow every 3s */
  useEffect(() => {
    const fetchLive = async () => {
      try { setBuffer(await getBuffer()); }  catch {}
      try { setHourly(await getHourly()); }  catch {}
      try { setLive(await getLatest()); }    catch {}
      try { setFlow(await getFlowSummary()); } catch {}
    };
    fetchLive();
    timerRef.current = setInterval(fetchLive, 3000);
    return () => clearInterval(timerRef.current);
  }, []);

  /* Fetch analysis once on mount */
  useEffect(() => {
    getAnalysis()
      .then(d => {
        setAna(d);
        setAlerts(d?.anomalies?.slice(-5).reverse() || []);
      })
      .catch(() => {});
  }, []);

  /* Build chart data from last 15 buffer readings */
  const last15 = buffer.slice(-15).map(p => ({
    time:     format(new Date(p.timestamp), 'HH:mm:ss'),
    distance: parseFloat(p.distance?.toFixed(2)),
    level:    parseFloat(Math.max(0, Math.min(100, (1 - p.distance / TANK_H) * 100)).toFixed(1)),
  }));

  const lvl     = live?.water_level_pct ?? 0;
  const dist    = live?.distance_mm;
  const state   = live?.roc?.state ?? 'Stable';
  const roc     = live?.roc?.roc ?? 0;
  const noise   = live?.roc?.noise_floor ?? 0;
  const lastAno = live?.last_anomaly;
  const insights= analysis?.insights ?? [];

  // Flow data
  const flowDir  = flow?.flow_direction ?? 'stable';
  const flowRate = flow?.current_flow_rate ?? 0;
  const tte      = flow?.est_time_to_empty;
  const ttf      = flow?.est_time_to_full;
  const flowTrend= flow?.trend ?? 'stable';

  return (
    <div>
      {/* ── Header ── */}
      <div style={{ marginBottom: '1.75rem', display: 'flex', alignItems: 'flex-end', gap: '1.5rem' }}>
        <div>
          <h1 style={{
            fontFamily: 'var(--font-display)', fontSize: '3rem',
            letterSpacing: '.08em', lineHeight: 1, color: 'var(--text)',
          }}>
            LIVE MONITOR
          </h1>
          <p style={{
            fontFamily: 'var(--font-mono)', fontSize: '.72rem',
            color: 'var(--muted)', marginTop: '.35rem', letterSpacing: '.06em',
          }}>
            Real-time tank telemetry · auto-refresh 3s
          </p>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '.5rem', alignItems: 'center' }}>
          <StateChip state={state} />
          {lastAno && <Badge type="danger">⚠ {lastAno.anomaly_class?.replace(/_/g,' ') || 'ANOMALY'}</Badge>}
          {lastAno && <TierBadge tier={lastAno.conf_tier} />}
        </div>
      </div>

      {/* ── KPI row ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'auto 1fr 1fr 1fr',
        gap: '1rem', marginBottom: '1.25rem', alignItems: 'stretch',
      }}>

        {/* Tank visual */}
        <Card style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem 1.75rem' }}>
          <TankVisual pct={lvl} />
        </Card>

        {/* Distance */}
        <Card style={{ borderColor: 'var(--border)', position: 'relative', overflow: 'hidden' }}>
          <div style={{
            position: 'absolute', top: 0, right: 0, width: 3, height: '100%',
            background: 'var(--cyan)', borderRadius: '0 8px 8px 0', opacity: .6,
          }} />
          <Stat
            label="Sensor Distance"
            value={dist != null ? dist.toFixed(1) : '—'}
            unit="mm"
            color="var(--cyan)"
          />
          <div style={{ marginTop: '.75rem', display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
            <StateChip state={state} />
          </div>
          <div style={{
            marginTop: '.6rem', fontFamily: 'var(--font-mono)',
            fontSize: '.65rem', color: 'var(--muted)',
          }}>
            {dist != null ? `${(100 - lvl).toFixed(1)}% headspace remaining` : '—'}
          </div>
        </Card>

        {/* Rate of Change */}
        <Card style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{
            position: 'absolute', top: 0, right: 0, width: 3, height: '100%',
            background: state === 'Emptying' ? 'var(--amber)' : state === 'Filling' ? 'var(--green)' : 'var(--muted)',
            borderRadius: '0 8px 8px 0', opacity: .6,
          }} />
          <Stat
            label="Rate of Change"
            value={roc >= 0 ? `+${roc.toFixed(3)}` : roc.toFixed(3)}
            unit="mm/sample"
            mono
            color={state === 'Emptying' ? 'var(--amber)' : state === 'Filling' ? 'var(--green)' : 'var(--muted2)'}
          />
          <div style={{
            marginTop: '.75rem', fontFamily: 'var(--font-mono)',
            fontSize: '.65rem', color: 'var(--muted)',
            display: 'grid', gap: '.15rem',
          }}>
            <div>noise floor: <span style={{ color: 'var(--text)' }}>{noise.toFixed(4)}</span></div>
            <div>|roc| / floor: <span style={{ color: noise > 0 ? 'var(--text)' : 'var(--muted)' }}>
              {noise > 0 ? (Math.abs(roc) / noise).toFixed(2) + '×' : '—'}
            </span></div>
          </div>
        </Card>

        {/* Anomaly status */}
        <Card style={{
          borderColor: lastAno ? 'rgba(239,68,68,.4)' : 'var(--border)',
          background: lastAno ? 'rgba(239,68,68,.04)' : 'var(--surface)',
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', top: 0, right: 0, width: 3, height: '100%',
            background: lastAno ? 'var(--red)' : 'var(--green)',
            borderRadius: '0 8px 8px 0',
          }} />
          <Stat
            label="Anomaly Status"
            value={lastAno ? (lastAno.anomaly_class?.replace(/_/g,' ') || 'ALERT') : 'NORMAL'}
            color={lastAno ? 'var(--red)' : 'var(--green)'}
          />
          <div style={{ marginTop: '.75rem', display: 'flex', gap: '.4rem', flexWrap: 'wrap' }}>
            {lastAno
              ? <>
                  <Badge type="danger">{lastAno.n_agree || '?'}/3 detectors</Badge>
                  <TierBadge tier={lastAno.conf_tier} />
                </>
              : <Badge type="success">✓ All clear</Badge>}
          </div>
          <div style={{
            marginTop: '.5rem', fontFamily: 'var(--font-mono)',
            fontSize: '.65rem', color: 'var(--muted)',
          }}>
            {alerts.length} events in history
          </div>
        </Card>
      </div>

      {/* ── Flow Analysis Row ── */}
      <Card style={{ marginBottom: '1.25rem' }}>
        <SectionTitle>FLOW ANALYSIS</SectionTitle>
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
          gap: '.75rem',
        }}>
          <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '.8rem 1rem' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.6rem', color: 'var(--muted)', letterSpacing: '.1em', textTransform: 'uppercase', marginBottom: '.3rem' }}>
              Flow Rate
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.3rem', color: flowDir === 'draining' ? 'var(--red)' : flowDir === 'filling' ? 'var(--green)' : 'var(--muted)' }}>
              {flowRate.toFixed(3)}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.6rem', color: 'var(--muted)' }}>mm/sample</div>
          </div>
          <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '.8rem 1rem' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.6rem', color: 'var(--muted)', letterSpacing: '.1em', textTransform: 'uppercase', marginBottom: '.3rem' }}>
              Direction
            </div>
            <FlowBadge direction={flowDir} />
          </div>
          <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '.8rem 1rem' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.6rem', color: 'var(--muted)', letterSpacing: '.1em', textTransform: 'uppercase', marginBottom: '.3rem' }}>
              Time to Empty
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', color: 'var(--text)' }}>
              {tte || '—'}
            </div>
          </div>
          <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '.8rem 1rem' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.6rem', color: 'var(--muted)', letterSpacing: '.1em', textTransform: 'uppercase', marginBottom: '.3rem' }}>
              Time to Full
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', color: 'var(--text)' }}>
              {ttf || '—'}
            </div>
          </div>
          <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '.8rem 1rem' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.6rem', color: 'var(--muted)', letterSpacing: '.1em', textTransform: 'uppercase', marginBottom: '.3rem' }}>
              Trend
            </div>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: '1rem',
              color: flowTrend === 'accelerating' ? 'var(--red)' : flowTrend === 'decelerating' ? 'var(--green)' : 'var(--muted)',
            }}>
              {flowTrend}
            </div>
          </div>
        </div>
      </Card>

      {/* ── Live chart ── */}
      <Card style={{ marginBottom: '1.25rem' }}>
        <SectionTitle>LAST 15 READINGS — DISTANCE (mm)</SectionTitle>
        {last15.length === 0
          ? <Spinner />
          : (
            <ResponsiveContainer width="100%" height={230}>
              <LineChart data={last15} margin={{ top: 8, right: 24, bottom: 4, left: 0 }}>
                <defs>
                  <linearGradient id="lineGlow" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%"   stopColor="var(--cyan)" stopOpacity={0.6} />
                    <stop offset="50%"  stopColor="var(--cyan)" stopOpacity={1} />
                    <stop offset="100%" stopColor="var(--cyan)" stopOpacity={0.6} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" />
                <XAxis
                  dataKey="time"
                  tick={{ fontFamily: 'var(--font-mono)', fontSize: 10, fill: 'var(--muted)' }}
                />
                <YAxis
                  tick={{ fontFamily: 'var(--font-mono)', fontSize: 10, fill: 'var(--muted)' }}
                  domain={['auto', 'auto']}
                />
                <Tooltip content={<ChartTip />} />
                <Line
                  type="monotone" dataKey="distance" name="Distance"
                  stroke="url(#lineGlow)" strokeWidth={2.5}
                  dot={{ fill: 'var(--cyan)', r: 4, strokeWidth: 0 }}
                  activeDot={{ r: 6, fill: '#fff', stroke: 'var(--cyan)', strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
      </Card>

      {/* ── Bottom: insights + hourly table ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: '1rem' }}>

        {/* Insights + alerts */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Card>
            <SectionTitle>INSIGHTS</SectionTitle>
            {insights.length === 0
              ? <p style={{ color: 'var(--muted)', fontFamily: 'var(--font-mono)', fontSize: '.75rem' }}>
                  Waiting for analysis…
                </p>
              : insights.map((ins, i) => (
                <div key={i} style={{
                  display: 'flex', gap: '.75rem', alignItems: 'flex-start',
                  marginBottom: '.5rem', padding: '.5rem .75rem',
                  background: 'var(--surface2)', borderRadius: 8,
                  borderLeft: `3px solid ${
                    ins.includes('⚠') ? 'var(--red)' :
                    ins.includes('🔴') ? 'var(--red)' :
                    ins.includes('🟡') ? 'var(--amber)' : 'var(--border2)'
                  }`,
                }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '.73rem', color: 'var(--text)', lineHeight: 1.5 }}>
                    {ins}
                  </span>
                </div>
              ))}
          </Card>

          {alerts.length > 0 && (
            <Card style={{ borderColor: 'rgba(239,68,68,.3)' }}>
              <SectionTitle>RECENT ANOMALIES</SectionTitle>
              {alerts.map((a, i) => (
                <div key={i} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '.4rem .6rem', marginBottom: '.3rem',
                  background: 'var(--red-dim)', borderRadius: 6,
                  fontFamily: 'var(--font-mono)', fontSize: '.7rem',
                }}>
                  <span style={{ color: 'var(--muted)' }}>{a.date?.slice(0, 16) || '—'}</span>
                  <span style={{ color: 'var(--amber)', marginLeft: '.5rem' }}>
                    {a.anomaly_class?.replace(/_/g, ' ') || '—'}
                  </span>
                  <span style={{ color: 'var(--red)' }}>{a.value?.toFixed(1)} mm</span>
                </div>
              ))}
            </Card>
          )}
        </div>

        {/* Hourly summary table */}
        <Card>
          <SectionTitle>HOURLY USAGE SUMMARY</SectionTitle>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-mono)', fontSize: '.72rem' }}>
              <thead>
                <tr>
                  {['Hour', 'Avg (mm)', 'Min', 'Max', 'Samples'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '.45rem .6rem',
                      color: 'var(--muted)', fontWeight: 400,
                      letterSpacing: '.07em', textTransform: 'uppercase', fontSize: '.62rem',
                      borderBottom: '1px solid var(--border)',
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {hourly.slice(-12).map((row, i) => (
                  <tr key={i} style={{
                    borderBottom: '1px solid var(--border)',
                    background: i % 2 ? 'rgba(255,255,255,.015)' : 'transparent',
                    transition: 'background .15s',
                  }}>
                    <td style={{ padding: '.45rem .6rem', color: 'var(--amber)' }}>{row.hour}</td>
                    <td style={{ padding: '.45rem .6rem', color: 'var(--text)' }}>{row.mean}</td>
                    <td style={{ padding: '.45rem .6rem', color: 'var(--green)' }}>{row.min}</td>
                    <td style={{ padding: '.45rem .6rem', color: 'var(--red)' }}>{row.max}</td>
                    <td style={{ padding: '.45rem .6rem', color: 'var(--muted)' }}>{row.count}</td>
                  </tr>
                ))}
                {hourly.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ padding: '1rem .6rem', color: 'var(--muted)', textAlign: 'center' }}>
                      Loading…
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <style>{`
        @keyframes wave {
          0%, 100% { transform: translateX(-20px); }
          50%       { transform: translateX(20px); }
        }
      `}</style>
    </div>
  );
}
