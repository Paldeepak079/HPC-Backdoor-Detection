import { useEffect, useState } from 'react';
import type React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Layout, { type Page } from './components/Layout';
import KPICard from './components/KPICard';
import NeuralPipeline from './components/NeuralPipeline';
import ScoreDistribution from './components/ScoreDistribution';
import TracesTable from './components/TracesTable';
import { useRunDataStore } from './store/runData';
import type { RunData, TraceRow } from './types/runData';
import './app.css';

type ExportedRun = {
  meta: { generated_at: string; detector_names: string[] };
  threshold: number;
  alpha: number;
  calibration: { n_flagged: number; n_total: number };
  rows: Array<{
    row_id: number; score: number; label: 0 | 1;
    top_features: Array<{ feature: string; z_score: number; direction: 'high' | 'low' }>;
    stage_scores: Record<string, number>;
  }>;
};

const LEGACY_DETECTORS = ['IForest', 'kNN', 'GMM', 'OCSVM', 'ECOD'];
const ACTIVE_DETECTORS = ['Mahalanobis', 'PCA'] as const;

function buildRunData(exported: ExportedRun): RunData {
  if (!Array.isArray(exported.rows) || exported.rows.length === 0) throw new Error('run.json contains no trace rows.');
  if (!Number.isFinite(exported.threshold) || !Number.isFinite(exported.alpha)) throw new Error('run.json has an invalid threshold or alpha.');
  if (!['mahalanobis', 'pca'].every(name => exported.meta.detector_names.includes(name))) {
    throw new Error('run.json does not contain the required Mahalanobis and PCA detector scores.');
  }
  const rows: TraceRow[] = exported.rows.map((row, index) => {
    if (!Number.isFinite(row.score) || (row.label !== 0 && row.label !== 1)) throw new Error(`run.json row ${index + 1} is invalid.`);
    const stage_scores = {
      Mahalanobis: row.stage_scores.mahalanobis,
      PCA: row.stage_scores.pca,
    };
    if (!Object.values(stage_scores).every(Number.isFinite)) throw new Error(`run.json row ${index + 1} is missing an active detector score.`);
    return {
      row_id: row.row_id,
      score: row.score,
      label: row.label,
      top_features: row.top_features.map(feature => ({ name: feature.feature, z_score: feature.z_score, direction: feature.direction })),
      stage_scores,
    };
  });
  return {
    meta: { timestamp: exported.meta.generated_at, n_rows: exported.calibration.n_total, n_flagged: exported.calibration.n_flagged, threshold: exported.threshold, alpha: exported.alpha, detectors: [...ACTIVE_DETECTORS], config_hash: 'exported run.json' },
    rows,
    calibration: { oof_scores: rows.map(row => row.score), oof_fpr_at_alpha: exported.calibration.n_flagged / exported.calibration.n_total, alpha: exported.alpha, tau: exported.threshold },
  };
}

function StatusPill({ children, tone = 'ok' }: { children: React.ReactNode; tone?: 'ok' | 'warn' }) {
  return <span className={`status-pill ${tone}`}>{children}</span>;
}

function DashboardPage({ page, data, dataError }: { page: Page; data: RunData; dataError: string | null }) {
  const { selectedRow, pipelineAnimating, setSelectedRow, setPipelineAnimating } = useRunDataStore();
  const flagged = data.rows.filter(row => row.label === 1);
  const meanScore = data.rows.reduce((sum, row) => sum + row.score, 0) / Math.max(data.rows.length, 1);
  const metricVariants = {
    hidden: { opacity: 0, y: 18 },
    visible: (index: number) => ({ opacity: 1, y: 0, transition: { delay: index * 0.07, duration: 0.35 } }),
  };

  const overview = (
    <>
      <header className="topbar">
        <div>
          <div className="eyebrow">SECURITY OPERATIONS / HPC TELEMETRY</div>
          <h1>Detection Command Center</h1>
          <p>Clean-only anomaly detection for hardware performance counter traces.</p>
        </div>
        <div className="topbar-actions">
          <StatusPill>● SYSTEM ONLINE</StatusPill>
        </div>
      </header>
      <section className="kpi-grid">
        {[
          ['Traces analyzed', data.meta.n_rows.toLocaleString(), 'exported run.json', 'var(--accent)'],
          ['Suspicious traces', data.meta.n_flagged.toLocaleString(), `${((data.meta.n_flagged / data.meta.n_rows) * 100).toFixed(2)}% above threshold`, 'var(--threat)'],
          ['Calibration threshold', data.meta.threshold.toFixed(4), `α = ${data.meta.alpha.toFixed(2)} · persisted threshold`, 'var(--warn)'],
          ['Mean anomaly score', meanScore.toFixed(4), 'fused ensemble score', 'var(--info-proxy)'],
        ].map(([label, value, sub, accentColor], index) => (
          <motion.div key={label} custom={index} initial="hidden" animate="visible" variants={metricVariants}>
            <KPICard label={label} value={value} sub={sub} accentColor={accentColor} />
          </motion.div>
        ))}
      </section>
      <div className="evidence-banner" role="status">
        <span className="banner-icon">✓</span>
        <div><strong>Measured detector output</strong><span>Scores below are exported from the verified batch artifact. A flag indicates deviation from benign HPC behaviour, not proof of a backdoor.</span></div>
        <span className="evidence-badge measured">MEASURED</span>
      </div>
      <section className="pipeline-panel glass-panel">
        <div className="glass-panel hero-panel">
          <div className="section-heading">
            <div><span className="eyebrow">DETECTION PIPELINE</span><h2>Neural detection pipeline</h2></div>
            <StatusPill tone={flagged.length ? 'warn' : 'ok'}>{flagged.length ? `${flagged.length} REVIEW` : 'ALL CLEAR'}</StatusPill>
          </div>
          <NeuralPipeline row={selectedRow ?? data.rows[0] ?? null} threshold={data.meta.threshold} animating={pipelineAnimating} onAnimationEnd={() => setPipelineAnimating(false)} />
        </div>
      </section>
      <section className="glass-panel chart-panel score-distribution-panel">
        <div className="section-heading"><div><span className="eyebrow">EXPORTED RUN SCORE DISTRIBUTION</span><h2>Score distribution</h2></div><span className="mono">τ {data.meta.threshold.toFixed(4)}</span></div>
        <ScoreDistribution scores={data.calibration.oof_scores} threshold={data.meta.threshold} nBins={40} height={230} />
        <div className="chart-note"><span className="dot ok" /> Clean baseline <span className="dot threat" /> Threshold exceedance</div>
      </section>
    </>
  );

  const traces = <div className="page-section"><header className="topbar"><div><div className="eyebrow">TRACE EXPLORER</div><h1>Trace explorer</h1><p>Search, filter and inspect the actual inference output.</p></div></header><div className="glass-panel table-panel"><TracesTable rows={data.rows} threshold={data.meta.threshold} selectedRowId={selectedRow?.row_id ?? null} onSelectRow={setSelectedRow} /></div></div>;

  const calibration = <div className="page-section"><header className="topbar"><div><div className="eyebrow">MODEL INSIGHTS</div><h1>Model insights</h1><p>Exported artifact metadata and benign-only calibration context.</p></div></header><div className="model-overview-grid"><div className="glass-panel info-card"><span className="eyebrow">ACTIVE ENSEMBLE</span><strong>Mahalanobis + PCA</strong><p>Two active detector scores are fused through the persisted artifact.</p><StatusPill>RUN.JSON LOADED</StatusPill></div><div className="glass-panel info-card"><span className="eyebrow">TRAINING POLICY</span><strong>Benign-only baseline</strong><p>Classification metrics require an independent labelled validation set.</p><StatusPill tone="warn">LABELS REQUIRED</StatusPill></div><div className="glass-panel calibration-card"><ScoreDistribution scores={data.calibration.oof_scores} threshold={data.meta.threshold} height={260} /></div></div><div className="glass-panel experiment-table"><div className="section-heading"><div><span className="eyebrow">EXPORTED DETECTORS</span><h2>Active score sources</h2></div><span className="evidence-badge measured">MEASURED</span></div><table><thead><tr><th>DETECTOR</th><th>STATUS</th></tr></thead><tbody>{data.meta.detectors.map(name => <tr key={name}><td className="mono">{name}</td><td>ACTIVE</td></tr>)}</tbody></table></div></div>;

  const content = page === 'overview' ? overview : page === 'traces' ? traces : calibration;
  return <>
    {dataError && <div className="error-banner" role="alert"><strong>Input rejected</strong><span>{dataError}</span></div>}
    {content}
    <AnimatePresence>
    {selectedRow && (
      <>
      <motion.div className="drawer-backdrop" aria-hidden="true" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setSelectedRow(null)} />
      <motion.aside className="drawer" aria-label="Trace detail" initial={{ opacity: 0, x: 44 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 44 }} transition={{ type: 'spring', stiffness: 360, damping: 32 }}>
        <div className="drawer-header"><div><span className="eyebrow">TRACE DETAIL</span><h2>Row #{selectedRow.row_id}</h2></div><button className="drawer-close" aria-label="Close trace detail" onClick={() => setSelectedRow(null)}>×</button></div>
        <div className="drawer-score">{selectedRow.score.toFixed(4)}</div>
        <p className="drawer-copy">{selectedRow.label === 1 ? 'Flagged — deviates from benign profile.' : 'Clean — within the calibrated benign profile.'}</p>
        <StatusPill tone={selectedRow.label === 1 ? 'warn' : 'ok'}>{selectedRow.label === 1 ? 'FLAGGED' : 'CLEAN'}</StatusPill>
        <div className="drawer-section"><h3>Top feature deviations</h3>{selectedRow.top_features.map(feature => <div className="feature-deviation" key={feature.name}><div><span>{feature.name}</span><strong>{feature.z_score > 0 ? '+' : ''}{feature.z_score.toFixed(2)}σ</strong></div><div className="feature-deviation-track"><span style={{ width: `${Math.min(Math.abs(feature.z_score), 5) / 5 * 100}%` }} /></div></div>)}</div>
        <div className="drawer-section"><h3>Primary detector scores</h3>{ACTIVE_DETECTORS.map(name => <div className="detector-row" key={name}><span>{name}</span><strong>{selectedRow.stage_scores[name].toFixed(4)}</strong></div>)}</div>
        <details className="advanced-scores"><summary>Legacy/Disabled Detectors</summary>{LEGACY_DETECTORS.map(name => <div className="detector-row legacy-score" key={name}><span>{name}</span><strong>Not part of active export</strong></div>)}</details>
      </motion.aside>
      </>
    )}
    </AnimatePresence>
  </>;
}

export default function App() {
  const { runData, setRunData } = useRunDataStore();
  const [page, setPage] = useState<Page>('overview');
  const [dataError, setDataError] = useState<string | null>(null);

  useEffect(() => {
    if (runData) return;
    fetch('/data/run.json').then(response => {
      if (!response.ok) throw new Error(`Required dashboard export run.json could not be loaded (${response.status}).`);
      return response.json();
    }).then((exported: ExportedRun) => setRunData(buildRunData(exported))).catch(error => setDataError(error instanceof Error ? error.message : 'Required dashboard export run.json could not be loaded.'));
  }, [runData, setRunData]);

  if (!runData && dataError) return <div className="loading-screen error-screen"><strong>HPC Sentinel could not load dashboard export</strong><p>{dataError}</p><button className="control-button primary" onClick={() => window.location.reload()}>Retry</button></div>;
  if (!runData) return <div className="loading-screen"><div className="loading-orb" /><p>Loading exported run.json…</p></div>;
  return <Layout currentPage={page} onNavigate={setPage}><DashboardPage page={page} data={runData} dataError={dataError} /></Layout>;
}
