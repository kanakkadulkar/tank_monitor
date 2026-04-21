import React, { useEffect, useState, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, ComposedChart, Area,
} from 'recharts';
import { Card, SectionTitle, Badge, Spinner } from '../components/ui';
import { getAnalysis } from '../services/api';
import { format, parseISO } from 'date-fns';

/* ── Helpers ──────────────────────────────────────────────────────────────── */
function downsample(arr, n) {
  if (!arr || arr.length <= n) return arr || [];
  const step = Math.ceil(arr.length / n);
  return arr.filter((_, i) => i % step === 0);
}

function shortDate(isoStr) {
  try { return format(parseISO(isoStr), 'MM/dd HH:mm'); }
  catch { return isoStr?.slice(0, 16) || ''; }
}

function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--surface2)', border: '1px solid var(--border2)',
      borderRadius: 8, padding: '.55rem .85rem',
      fontFamily: 'var(--font-mono)', fontSize: '.7rem',
    }}>
      <div style={{ color: 'var(--muted)', marginBottom: '.3rem' }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || 'var(--text)' }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(2) : p.value}
        </div>
      ))}
    </div>
  );
}

/* ── Section header with refresh button ──────────────────────────────────── */
function PageHeader({ onRefresh, loading }) {
  return (
    <div style={{ marginBottom: '1.75rem', display: 'flex', alignItems: 'flex-end', gap: '1rem' }}>
      <div>
        <h1 style={{
          fontFamily: 'var(--font-display)', fontSize: '3rem',
          letterSpacing: '.08em', lineHeight: 1,
        }}>
          DEEP ANALYSIS
        </h1>
        <p style={{
          fontFamily: 'var(--font-mono)', fontSize: '.72rem',
          color: 'var(--muted)', marginTop: '.35rem', letterSpacing: '.06em',
        }}>
          STL decomposition · MAD + RoC + Adaptive CUSUM · 3-method voting
        </p>
      </div>
      <button
        onClick={onRefresh}
        disabled={loading}
        style={{
          marginLeft: 'auto',
          background: 'var(--surface2)', border: '1px solid var(--border2)',
          color: loading ? 'var(--muted)' : 'var(--cyan)',
          borderRadius: 8, padding: '.5rem 1.1rem',
          fontFamily: 'var(--font-mono)', fontSize: '.72rem',
          letterSpacing: '.06em', cursor: loading ? 'default' : 'pointer',
          transition: 'border-color .2s, color .2s',
        }}
      >
        {loading ? '⟳ LOADING…' : '⟳ REFRESH'}
      </button>
    </div>
  );
}

/* ── Stat mini card ───────────────────────────────────────────────────────── */
function MiniStat({ label, value, color }) {
  return (
    <div style={{
      background: 'var(--surface2)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '.7rem 1rem', flex: '1 1 0',
    }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.62rem',
                    letterSpacing: '.1em', textTransform: 'uppercase',
                    color: 'var(--muted)', marginBottom: '.3rem' }}>
        {label}
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem',
                    color: color || 'var(--text)' }}>
        {value}
      </div>
    </div>
  );
}

/* ── Main Analytics ───────────────────────────────────────────────────────── */
export default function Analytics() {
  const [analysis, setAna]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab]         = useState('stl');   // 'stl' | 'anomaly'

  const load = useCallback(() => {
    setLoading(true);
    getAnalysis()
      .then(a => { setAna(a); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  /* ── Derived data ── */
  const stl = analysis?.stl;
  const anomalySet = new Set((analysis?.anomalies || []).map(a => a.index));

  const stlData = stl
    ? downsample(
        stl.dates.map((d, i) => ({
          date:      shortDate(d),
          original:  +stl.original[i].toFixed(2),
          trend:     +stl.trend[i].toFixed(2),
          seasonal:  +stl.seasonal[i].toFixed(2),
          resid:     +stl.resid[i].toFixed(2),
          anomaly:   anomalySet.has(i) ? stl.original[i] : null,
        })),
        300
      )
    : [];

  const insights = analysis?.insights || [];
  const anomalies = analysis?.anomalies || [];

  /* ── STL stats ── */
  const stlStats = stl ? {
    mad:       stl.mad?.toFixed(3),
    threshold: stl.mad_threshold?.toFixed(3),
    anomalyN:  anomalies.length,
    residStd:  (stl.resid?.length > 0
      ? Math.sqrt(stl.resid.reduce((s, v) => s + v * v, 0) / stl.resid.length).toFixed(3)
      : '—'),
  } : null;

  /* ── Anomaly class breakdown ── */
  const classCounts = {};
  anomalies.forEach(a => {
    const cls = a.anomaly_class || 'unclassified';
    classCounts[cls] = (classCounts[cls] || 0) + 1;
  });

  /* ── Tab nav ── */
  const tabs = [
    { id: 'stl',     label: 'STL Decomposition' },
    { id: 'anomaly', label: 'Anomaly Analysis' },
  ];

  const tabStyle = (id) => ({
    fontFamily: 'var(--font-mono)', fontSize: '.72rem',
    letterSpacing: '.08em', textTransform: 'uppercase',
    padding: '.6rem 1.2rem',
    background: tab === id ? 'var(--surface2)' : 'transparent',
    border: '1px solid',
    borderColor: tab === id ? 'var(--border2)' : 'transparent',
    color: tab === id ? 'var(--amber)' : 'var(--muted)',
    borderRadius: 8, cursor: 'pointer',
    transition: 'all .2s',
  });

  return (
    <div>
      <PageHeader onRefresh={load} loading={loading} />

      {/* ── Insights row ── */}
      {insights.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.5rem', marginBottom: '1.5rem' }}>
          {insights.map((ins, i) => (
            <div key={i} style={{
              background: 'var(--surface)', border: '1px solid var(--border2)',
              borderRadius: 8, padding: '.4rem .85rem',
              fontFamily: 'var(--font-mono)', fontSize: '.72rem', color: 'var(--text)',
              borderLeft: `3px solid ${
                ins.includes('⚠') || ins.includes('🔴') ? 'var(--red)' :
                ins.includes('🟡') ? 'var(--amber)' : 'var(--cyan)'
              }`,
            }}>
              {ins}
            </div>
          ))}
        </div>
      )}

      {/* ── Stats row ── */}
      {stlStats && (
        <div style={{ display: 'flex', gap: '.75rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
          <MiniStat label="MAD"           value={stlStats.mad}       color="var(--cyan)" />
          <MiniStat label="MAD Threshold" value={stlStats.threshold} color="var(--amber)" />
          <MiniStat label="Residual RMS"  value={stlStats.residStd}  color="var(--blue)" />
          <MiniStat label="Anomaly Count" value={stlStats.anomalyN}  color={stlStats.anomalyN > 0 ? 'var(--red)' : 'var(--green)'} />
          <MiniStat label="STL Period"    value={`${stl.period}h`}   color="var(--muted)" />
        </div>
      )}

      {/* ── Tab switcher ── */}
      <div style={{ display: 'flex', gap: '.5rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        {tabs.map(t => (
          <button key={t.id} style={tabStyle(t.id)} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {loading && <Spinner />}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* TAB 1: STL Decomposition                                           */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {!loading && tab === 'stl' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

          {/* Original + Trend */}
          <Card>
            <div style={{ display: 'flex', alignItems: 'center', gap: '.75rem', marginBottom: '.75rem' }}>
              <SectionTitle>ORIGINAL SIGNAL + TREND</SectionTitle>
              <div style={{ display: 'flex', gap: '.4rem', marginLeft: 'auto' }}>
                <Badge type="info">Cyan = Original</Badge>
                <Badge type="warning">Amber = Trend</Badge>
                <Badge type="danger">● Anomalies</Badge>
              </div>
            </div>
            {stlData.length === 0 ? <Spinner /> : (
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={stlData} margin={{ top: 8, right: 24, bottom: 4, left: 0 }}>
                  <defs>
                    <linearGradient id="origFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"   stopColor="var(--cyan)" stopOpacity={0.15} />
                      <stop offset="100%" stopColor="var(--cyan)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" />
                  <XAxis dataKey="date"
                    tick={{ fontFamily: 'var(--font-mono)', fontSize: 9, fill: 'var(--muted)' }}
                    interval={Math.max(1, Math.floor(stlData.length / 10))}
                  />
                  <YAxis tick={{ fontFamily: 'var(--font-mono)', fontSize: 9, fill: 'var(--muted)' }} />
                  <Tooltip content={<ChartTip />} />
                  <Area
                    type="monotone" dataKey="original" name="Original"
                    stroke="var(--cyan)" fill="url(#origFill)" strokeWidth={1.5} dot={false}
                  />
                  <Line
                    type="monotone" dataKey="trend" name="Trend"
                    stroke="var(--amber)" strokeWidth={2.5} dot={false}
                  />
                  {/* Anomaly scatter as dots */}
                  <Line
                    type="monotone" dataKey="anomaly" name="Anomaly"
                    stroke="none"
                    dot={(props) => {
                      if (props.payload.anomaly == null) return null;
                      return (
                        <circle
                          key={props.index}
                          cx={props.cx} cy={props.cy} r={5}
                          fill="var(--red)" stroke="rgba(239,68,68,.4)" strokeWidth={4}
                        />
                      );
                    }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </Card>

          {/* Seasonal + Residual side by side */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Card>
              <SectionTitle>SEASONAL COMPONENT</SectionTitle>
              {stlData.length === 0 ? <Spinner /> : (
                <ResponsiveContainer width="100%" height={200}>
                  <ComposedChart data={stlData} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
                    <defs>
                      <linearGradient id="seasonFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%"   stopColor="#3b82f6" stopOpacity={0.2} />
                        <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" />
                    <XAxis dataKey="date"
                      tick={{ fontFamily: 'var(--font-mono)', fontSize: 9, fill: 'var(--muted)' }}
                      interval={Math.max(1, Math.floor(stlData.length / 6))}
                    />
                    <YAxis tick={{ fontFamily: 'var(--font-mono)', fontSize: 9, fill: 'var(--muted)' }} />
                    <Tooltip content={<ChartTip />} />
                    <ReferenceLine y={0} stroke="var(--border2)" strokeDasharray="3 3" />
                    <Area
                      type="monotone" dataKey="seasonal" name="Seasonal"
                      stroke="var(--blue)" fill="url(#seasonFill)" strokeWidth={1.5} dot={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card>
              <SectionTitle>RESIDUALS — ANOMALY SIGNAL</SectionTitle>
              <div style={{ marginBottom: '.5rem', display: 'flex', gap: '.4rem' }}>
                <Badge type="danger">Red zone = anomaly</Badge>
              </div>
              {stlData.length === 0 ? <Spinner /> : (
                <ResponsiveContainer width="100%" height={170}>
                  <ComposedChart data={stlData} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
                    <defs>
                      <linearGradient id="residFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%"   stopColor="var(--red)" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="var(--red)" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" />
                    <XAxis dataKey="date"
                      tick={{ fontFamily: 'var(--font-mono)', fontSize: 9, fill: 'var(--muted)' }}
                      interval={Math.max(1, Math.floor(stlData.length / 6))}
                    />
                    <YAxis tick={{ fontFamily: 'var(--font-mono)', fontSize: 9, fill: 'var(--muted)' }} />
                    <Tooltip content={<ChartTip />} />
                    <ReferenceLine y={0} stroke="var(--border2)" strokeDasharray="3 3" />
                    <Area
                      type="monotone" dataKey="resid" name="Residual"
                      stroke="var(--red)" fill="url(#residFill)" strokeWidth={1.5} dot={false}
                    />
                    <Line
                      type="monotone" dataKey="anomaly" name="Anomaly"
                      stroke="none"
                      dot={(props) => {
                        if (props.payload.anomaly == null) return null;
                        return (
                          <circle
                            key={props.index}
                            cx={props.cx} cy={props.cy} r={4}
                            fill="var(--red)" stroke="rgba(239,68,68,.5)" strokeWidth={5}
                          />
                        );
                      }}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </Card>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* TAB 2: Anomaly Analysis                                            */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {!loading && tab === 'anomaly' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

          {/* Summary cards */}
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <Card style={{ flex: '1 1 200px' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.62rem',
                            color: 'var(--muted)', letterSpacing: '.1em',
                            textTransform: 'uppercase', marginBottom: '.5rem' }}>
                Total Anomalies
              </div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: '3rem',
                            color: anomalies.length > 0 ? 'var(--red)' : 'var(--green)', lineHeight: 1 }}>
                {anomalies.length}
              </div>
              <div style={{ marginTop: '.5rem' }}>
                {anomalies.length > 0
                  ? <Badge type="danger">Adaptive threshold exceeded</Badge>
                  : <Badge type="success">Within normal bounds</Badge>}
              </div>
            </Card>
            <Card style={{ flex: '1 1 200px' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.62rem',
                            color: 'var(--muted)', letterSpacing: '.1em',
                            textTransform: 'uppercase', marginBottom: '.5rem' }}>
                Detection Method
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.85rem',
                            color: 'var(--text)', lineHeight: 1.8 }}>
                <div>▸ STL Residual MAD (point)</div>
                <div>▸ RoC Threshold ±2.0 (contextual)</div>
                <div>▸ Adaptive CUSUM (collective)</div>
                <div>▸ Voting: n_agree / 3</div>
                <div>▸ Alert suppression (5-hit)</div>
              </div>
            </Card>

            {/* Class breakdown */}
            <Card style={{ flex: '1 1 200px' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.62rem',
                            color: 'var(--muted)', letterSpacing: '.1em',
                            textTransform: 'uppercase', marginBottom: '.5rem' }}>
                Classification Breakdown
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.8rem', lineHeight: 2 }}>
                {Object.keys(classCounts).length === 0
                  ? <span style={{ color: 'var(--green)' }}>No anomalies</span>
                  : Object.entries(classCounts).map(([cls, cnt]) => (
                    <div key={cls}>
                      <span style={{ color: 'var(--amber)' }}>{cls.replace(/_/g, ' ')}</span>
                      {': '}
                      <span style={{ color: 'var(--red)' }}>{cnt}</span>
                    </div>
                  ))
                }
              </div>
            </Card>

            {stlStats && (
              <Card style={{ flex: '1 1 200px' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.62rem',
                              color: 'var(--muted)', letterSpacing: '.1em',
                              textTransform: 'uppercase', marginBottom: '.5rem' }}>
                  Adaptive Parameters
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.8rem',
                              color: 'var(--text)', lineHeight: 2 }}>
                  <div>MAD: <span style={{ color: 'var(--cyan)' }}>{stlStats.mad}</span></div>
                  <div>Threshold (99.5%ile): <span style={{ color: 'var(--amber)' }}>{stlStats.threshold}</span></div>
                  <div>Resid RMS: <span style={{ color: 'var(--blue)' }}>{stlStats.residStd}</span></div>
                </div>
              </Card>
            )}
          </div>

          {/* Anomaly table */}
          <Card>
            <SectionTitle>ANOMALY EVENT LOG ({anomalies.length} events)</SectionTitle>
            <div style={{ overflowX: 'auto', maxHeight: 400, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse',
                              fontFamily: 'var(--font-mono)', fontSize: '.72rem' }}>
                <thead style={{ position: 'sticky', top: 0, background: 'var(--surface)' }}>
                  <tr>
                    {['#', 'Timestamp', 'Distance (mm)', 'Class', 'Tier', 'Detectors', 'MAD-Z'].map(h => (
                      <th key={h} style={{
                        textAlign: 'left', padding: '.5rem .7rem',
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
                  {anomalies.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ padding: '1.5rem .7rem', color: 'var(--muted)', textAlign: 'center' }}>
                        No anomalies detected
                      </td>
                    </tr>
                  ) : anomalies.map((a, i) => (
                    <tr key={i} style={{
                      borderBottom: '1px solid var(--border)',
                      background: i % 2 ? 'rgba(239,68,68,.03)' : 'transparent',
                    }}>
                      <td style={{ padding: '.45rem .7rem', color: 'var(--muted)' }}>{i + 1}</td>
                      <td style={{ padding: '.45rem .7rem', color: 'var(--amber)' }}>
                        {a.date?.replace('T', ' ').slice(0, 19) || '—'}
                      </td>
                      <td style={{ padding: '.45rem .7rem', color: 'var(--red)' }}>
                        {a.value?.toFixed(2)}
                      </td>
                      <td style={{ padding: '.45rem .7rem', color: 'var(--cyan)' }}>
                        {a.anomaly_class?.replace(/_/g, ' ') || '—'}
                      </td>
                      <td style={{ padding: '.45rem .7rem' }}>
                        <span style={{
                          color: a.conf_tier === 'critical' ? 'var(--red)' :
                                 a.conf_tier === 'alert' ? 'var(--amber)' :
                                 'var(--muted)',
                          fontWeight: a.conf_tier === 'critical' ? 600 : 400,
                        }}>
                          {a.conf_tier?.toUpperCase() || '—'}
                        </span>
                      </td>
                      <td style={{ padding: '.45rem .7rem', color: 'var(--text)' }}>
                        {a.n_agree || '—'}/3
                      </td>
                      <td style={{ padding: '.45rem .7rem', color: 'var(--text)' }}>
                        {a.mad_z?.toFixed(2) || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
