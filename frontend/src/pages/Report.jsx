import React, { useEffect, useState, useCallback } from 'react';
import { Card, SectionTitle, Badge, Spinner } from '../components/ui';
import { getAnalysis, getLatest } from '../services/api';

/* ── Stat card for report ─────────────────────────────────────────────────── */
function ReportStat({ label, value, color }) {
  return (
    <div style={{
      background: 'var(--surface2)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '1rem 1.2rem', flex: '1 1 180px',
    }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.62rem',
                    letterSpacing: '.1em', textTransform: 'uppercase',
                    color: 'var(--muted)', marginBottom: '.3rem' }}>
        {label}
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.5rem',
                    color: color || 'var(--text)', fontWeight: 600 }}>
        {value ?? '—'}
      </div>
    </div>
  );
}

/* ── Main Report Page ─────────────────────────────────────────────────────── */
export default function Report() {
  const [analysis, setAna] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    getAnalysis()
      .then(a => { setAna(a); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  // Real-time overlay polling
  useEffect(() => {
    const timer = setInterval(() => {
      getLatest().then((latest) => {
        setAna(prev => {
          if (!prev || prev.error) return prev;
          return {
            ...prev,
            current_level: {
              distance_mm: latest.distance_mm,
              water_level_pct: latest.water_level_pct,
              timestamp: latest.timestamp,
            },
            roc_state: latest.roc,
            flow: latest.flow,
          };
        });
      }).catch(() => {});
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  if (loading) return <Spinner />;
  if (!analysis || analysis.error) {
    return (
      <Card style={{ textAlign: 'center', padding: '3rem' }}>
        <p style={{ color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
          {analysis?.error || 'No analysis data available.'}
        </p>
      </Card>
    );
  }

  const current  = analysis.current_level || {};
  const roc      = analysis.roc_state || {};
  const flow     = analysis.flow || {};
  const stl      = analysis.stl;
  const anomalies= analysis.anomalies || [];
  const insights = analysis.insights || [];
  const hourly   = analysis.hourly_summary || [];

  // Anomaly class breakdown
  const classCounts = {};
  anomalies.forEach(a => {
    const cls = a.anomaly_class || 'unclassified';
    classCounts[cls] = (classCounts[cls] || 0) + 1;
  });

  const now = new Date().toLocaleString();

  return (
    <div>
      {/* ── Header ── */}
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{
          fontFamily: 'var(--font-display)', fontSize: '2.5rem',
          letterSpacing: '.08em', lineHeight: 1,
        }}>
          ANALYSIS REPORT
        </h1>
        <p style={{
          fontFamily: 'var(--font-mono)', fontSize: '.72rem',
          color: 'var(--muted)', marginTop: '.35rem', letterSpacing: '.06em',
        }}>
          Generated: {now} · Adaptive STL + MAD + RoC + CUSUM pipeline
        </p>
      </div>

      {/* ── Current Status ── */}
      <Card style={{ marginBottom: '1.25rem' }}>
        <SectionTitle>CURRENT TANK STATUS</SectionTitle>
        <div style={{ display: 'flex', gap: '.75rem', flexWrap: 'wrap' }}>
          <ReportStat label="Water Level" value={`${current.water_level_pct}%`} color="var(--cyan)" />
          <ReportStat label="Sensor Distance" value={`${current.distance_mm} mm`} />
          <ReportStat label="Flow State" value={roc.state || 'Stable'} 
            color={roc.state === 'Filling' ? 'var(--green)' : roc.state === 'Emptying' ? 'var(--amber)' : 'var(--muted)'} />
          <ReportStat label="Rate of Change" value={roc.roc?.toFixed(4) || '0'} />
        </div>
      </Card>

      {/* ── Flow Analysis ── */}
      <Card style={{ marginBottom: '1.25rem' }}>
        <SectionTitle>FLOW ANALYSIS</SectionTitle>
        <div style={{ display: 'flex', gap: '.75rem', flexWrap: 'wrap' }}>
          <ReportStat label="Flow Rate" value={`${flow.current_flow_rate || 0} mm/s`} />
          <ReportStat label="Direction" value={flow.flow_direction || 'stable'} />
          <ReportStat label="Est. Time to Empty" value={flow.est_time_to_empty || '—'} />
          <ReportStat label="Est. Time to Full" value={flow.est_time_to_full || '—'} />
          <ReportStat label="Trend" value={flow.trend || 'stable'} />
        </div>
      </Card>

      {/* ── Detection Methodology ── */}
      <Card style={{ marginBottom: '1.25rem' }}>
        <SectionTitle>DETECTION METHODOLOGY</SectionTitle>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '.75rem' }}>
          <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '1rem', borderLeft: '3px solid var(--cyan)' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.8rem', color: 'var(--cyan)', fontWeight: 600, marginBottom: '.3rem' }}>
              1. STL Decomposition
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.72rem', color: 'var(--muted)', lineHeight: 1.6 }}>
              Decomposes raw signal into Trend + Seasonal + Residual using robust
              Seasonal-Trend decomposition. Period: {stl?.period || '24'}h. All detection
              operates on the residual (detrended, deseasonalized).
            </div>
          </div>
          <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '1rem', borderLeft: '3px solid var(--amber)' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.8rem', color: 'var(--amber)', fontWeight: 600, marginBottom: '.3rem' }}>
              2. MAD (Median Absolute Deviation)
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.72rem', color: 'var(--muted)', lineHeight: 1.6 }}>
              Point anomaly detector. Fires when |residual - median| exceeds
              adaptive threshold (99.5th percentile). MAD: {stl?.mad?.toFixed(4) || '—'},
              Threshold: {stl?.mad_threshold?.toFixed(4) || '—'}.
            </div>
          </div>
          <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '1rem', borderLeft: '3px solid var(--green)' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.8rem', color: 'var(--green)', fontWeight: 600, marginBottom: '.3rem' }}>
              3. Rate of Change (RoC)
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.72rem', color: 'var(--muted)', lineHeight: 1.6 }}>
              Contextual anomaly detector. Fires when |RoC| {">"} ±2.0 mm/sample
              (Chandola taxonomy threshold). Catches sudden drains, refill events,
              and theft scenarios.
            </div>
          </div>
          <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '1rem', borderLeft: '3px solid var(--red)' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.8rem', color: 'var(--red)', fontWeight: 600, marginBottom: '.3rem' }}>
              4. Adaptive CUSUM
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '.72rem', color: 'var(--muted)', lineHeight: 1.6 }}>
              Collective anomaly detector. Tracks cumulative deviations from baseline.
              k = MAD(residuals), h = 99th %ile of cumulative dev. Catches slow leaks
              and gradual drifts missed by point detectors.
            </div>
          </div>
        </div>
        <div style={{
          marginTop: '.75rem', padding: '.6rem 1rem',
          background: 'var(--surface2)', borderRadius: 8,
          fontFamily: 'var(--font-mono)', fontSize: '.72rem', color: 'var(--muted)',
          borderLeft: '3px solid var(--border2)',
        }}>
          <strong style={{ color: 'var(--text)' }}>Hybrid Decision:</strong> is_anomaly = MAD OR RoC OR CUSUM.
          Confidence = n_agree / 3 (3-method voting). Alert suppression after 5 consecutive same-class alerts.
        </div>
      </Card>

      {/* ── Insights ── */}
      {insights.length > 0 && (
        <Card style={{ marginBottom: '1.25rem' }}>
          <SectionTitle>INSIGHTS</SectionTitle>
          {insights.map((ins, i) => (
            <div key={i} style={{
              background: 'var(--surface2)', borderRadius: 8,
              padding: '.5rem 1rem', marginBottom: '.4rem',
              fontFamily: 'var(--font-mono)', fontSize: '.75rem', color: 'var(--text)',
              borderLeft: '3px solid var(--border2)',
            }}>
              {ins}
            </div>
          ))}
        </Card>
      )}

      {/* ── STL Summary ── */}
      {stl && (
        <Card style={{ marginBottom: '1.25rem' }}>
          <SectionTitle>STL DECOMPOSITION SUMMARY</SectionTitle>
          <div style={{ display: 'flex', gap: '.75rem', flexWrap: 'wrap' }}>
            <ReportStat label="MAD" value={stl.mad?.toFixed(4)} color="var(--cyan)" />
            <ReportStat label="MAD Threshold (99.5%ile)" value={stl.mad_threshold?.toFixed(4)} color="var(--amber)" />
            <ReportStat label="STL Period" value={`${stl.period}h`} />
            <ReportStat label="Data Points" value={stl.original?.length || 0} />
          </div>
        </Card>
      )}

      {/* ── Anomaly Classification Breakdown ── */}
      <Card style={{ marginBottom: '1.25rem' }}>
        <SectionTitle>ANOMALY CLASSIFICATION ({anomalies.length} events)</SectionTitle>
        {anomalies.length === 0 ? (
          <p style={{ color: 'var(--green)', fontFamily: 'var(--font-mono)', fontSize: '.85rem' }}>
            ✓ No anomalies detected — system nominal.
          </p>
        ) : (
          <>
            {/* Class summary badges */}
            <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
              {Object.entries(classCounts).map(([cls, cnt]) => (
                <Badge key={cls} type="danger">{cls.replace(/_/g, ' ')}: {cnt}</Badge>
              ))}
            </div>

            {/* Anomaly table */}
            <div style={{ overflowX: 'auto', maxHeight: 350, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse',
                              fontFamily: 'var(--font-mono)', fontSize: '.72rem' }}>
                <thead style={{ position: 'sticky', top: 0, background: 'var(--surface)' }}>
                  <tr>
                    {['#', 'Timestamp', 'Distance (mm)', 'Class', 'Tier', 'Detectors', 'MAD-Z'].map(h => (
                      <th key={h} style={{
                        textAlign: 'left', padding: '.5rem .7rem',
                        color: 'var(--muted)', fontWeight: 400, fontSize: '.62rem',
                        letterSpacing: '.07em', textTransform: 'uppercase',
                        borderBottom: '1px solid var(--border)',
                      }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {anomalies.slice(0, 50).map((a, i) => (
                    <tr key={i} style={{
                      borderBottom: '1px solid var(--border)',
                      background: i % 2 ? 'rgba(239,68,68,.03)' : 'transparent',
                    }}>
                      <td style={{ padding: '.4rem .7rem', color: 'var(--muted)' }}>{i + 1}</td>
                      <td style={{ padding: '.4rem .7rem', color: 'var(--amber)' }}>
                        {a.date?.replace('T', ' ').slice(0, 19) || '—'}
                      </td>
                      <td style={{ padding: '.4rem .7rem', color: 'var(--red)' }}>
                        {a.value?.toFixed(2)}
                      </td>
                      <td style={{ padding: '.4rem .7rem', color: 'var(--cyan)' }}>
                        {a.anomaly_class?.replace(/_/g, ' ') || '—'}
                      </td>
                      <td style={{ padding: '.4rem .7rem',
                        color: a.conf_tier === 'critical' ? 'var(--red)' :
                               a.conf_tier === 'alert' ? 'var(--amber)' : 'var(--muted)',
                      }}>
                        {a.conf_tier?.toUpperCase() || '—'}
                      </td>
                      <td style={{ padding: '.4rem .7rem', color: 'var(--text)' }}>
                        {a.n_agree || '—'}/3
                      </td>
                      <td style={{ padding: '.4rem .7rem', color: 'var(--text)' }}>
                        {a.mad_z?.toFixed(2) || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      {/* ── Hourly Summary ── */}
      <Card>
        <SectionTitle>HOURLY USAGE SUMMARY</SectionTitle>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse',
                          fontFamily: 'var(--font-mono)', fontSize: '.72rem' }}>
            <thead>
              <tr>
                {['Hour', 'Avg (mm)', 'Min', 'Max', 'Samples'].map(h => (
                  <th key={h} style={{
                    textAlign: 'left', padding: '.45rem .6rem',
                    color: 'var(--muted)', fontWeight: 400, fontSize: '.62rem',
                    letterSpacing: '.07em', textTransform: 'uppercase',
                    borderBottom: '1px solid var(--border)',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {hourly.map((row, i) => (
                <tr key={i} style={{
                  borderBottom: '1px solid var(--border)',
                  background: i % 2 ? 'rgba(255,255,255,.015)' : 'transparent',
                }}>
                  <td style={{ padding: '.4rem .6rem', color: 'var(--amber)' }}>{row.hour}</td>
                  <td style={{ padding: '.4rem .6rem', color: 'var(--text)' }}>{row.mean}</td>
                  <td style={{ padding: '.4rem .6rem', color: 'var(--green)' }}>{row.min}</td>
                  <td style={{ padding: '.4rem .6rem', color: 'var(--red)' }}>{row.max}</td>
                  <td style={{ padding: '.4rem .6rem', color: 'var(--muted)' }}>{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div style={{
        marginTop: '2rem', padding: '1rem', textAlign: 'center',
        fontFamily: 'var(--font-mono)', fontSize: '.65rem', color: 'var(--muted)',
        borderTop: '1px solid var(--border)',
      }}>
        Tank Monitor · STL + MAD + RoC + CUSUM Pipeline · Chandola et al. (2009) Taxonomy
      </div>
    </div>
  );
}
