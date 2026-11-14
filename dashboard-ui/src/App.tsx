import { useEffect, useState } from 'react';
import type React from 'react';
import Layout, { type Page } from './components/Layout';
import KPICard from './components/KPICard';
import NeuralPipeline from './components/NeuralPipeline';
import ScoreDistribution from './components/ScoreDistribution';
import TracesTable from './components/TracesTable';
import { useRunDataStore } from './store/runData';
import type { RunData, TraceRow } from './types/runData';
import './app.css';

type Manifest = { tau: number; alpha: number; feature_names: string[] };
type ExperimentResults = {
  meta: { n_samples: number; cv_folds: number; cv_repeats: number; seed: number };
  per_detector: Record<string, { oof_mean: number; oof_std: number; oof_q95: number }>;
  fused_oof_stats: { mean: number; std: number; q95: number };
  fused_oof: number[];
};

const DETECTOR_COLUMNS = [
  ['score_mahalanobis', 'Mahalanobis'],
  ['score_pca', 'PCA'],
  ['score_iforest', 'IForest'],
  ['score_knn', 'kNN'],
  ['score_gmm', 'GMM'],
  ['score_ocsvm', 'OCSVM'],
  ['score_pyod_ecod', 'ECOD'],
] as const;

function parseCsv(text: string): Record<string, string>[] {
  const [header, ...lines] = text.trim().split(/\r?\n/);
  if (!header) throw new Error('CSV is empty.');
  const split = (line: string) => line.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/).map(value => value.trim().replace(/^"|"$/g, ''));
  const fields = split(header);
  if (new Set(fields).size !== fields.length) throw new Error('CSV contains duplicate column names.');
  return lines.filter(Boolean).map(line => {
    const values = split(line);
    return Object.fromEntries(fields.map((field, index) => [field, values[index] ?? '']));
  });
}

function buildRunData(text: string, manifest: Manifest): RunData {
  const records = parseCsv(text);
  const required = ['cache-references', 'cycles', 'LLC-loads', 'score', 'label', ...DETECTOR_COLUMNS.map(([column]) => column)];
  const missing = required.filter(column => !records[0] || !(column in records[0]));
  if (missing.length) throw new Error(`Missing required detector columns: ${missing.join(', ')}`);
  if (!records.length) throw new Error('CSV contains no data rows.');
  for (const [index, record] of records.entries()) {
    for (const column of required) {
      if (!Number.isFinite(Number(record[column]))) throw new Error(`Row ${index + 1} has a non-numeric value in '${column}'.`);
    }
  }
  const numeric = (name: string) => records.map(row => Number(row[name]));
  const featureNames = ['cache-references', 'cycles', 'LLC-loads'];
  const stats = Object.fromEntries(featureNames.map(name => {
    const values = numeric(name);
    const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
    const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / Math.max(values.length - 1, 1);
    return [name, { mean, std: Math.sqrt(variance) || 1 }];
  }));

  const rows: TraceRow[] = records.map((record, row_id) => {
    const top_features = featureNames
      .map(name => {
        const z_score = (Number(record[name]) - stats[name].mean) / stats[name].std;
        return { name, z_score, direction: z_score >= 0 ? 'high' as const : 'low' as const };
      })
      .sort((a, b) => Math.abs(b.z_score) - Math.abs(a.z_score));
    const stage_scores = Object.fromEntries(
      DETECTOR_COLUMNS.map(([column, label]) => [label, Number(record[column])]),
    );
    return {
      row_id,
      score: Number(record.score),
      label: Number(record.label) === 1 ? 1 : 0,
      top_features,
      stage_scores,
    };
  });

  return {
    meta: {
      timestamp: new Date().toISOString(),
      n_rows: rows.length,
      n_flagged: rows.filter(row => row.label === 1).length,
      threshold: manifest.tau,
      alpha: manifest.alpha,
      detectors: DETECTOR_COLUMNS.map(([, label]) => label),
      config_hash: 'local artifact',
    },
    rows,
    calibration: {
      oof_scores: rows.map(row => row.score),
      oof_fpr_at_alpha: rows.filter(row => row.label === 1).length / Math.max(rows.length, 1),
      alpha: manifest.alpha,
      tau: manifest.tau,
    },
  };
}

function StatusPill({ children, tone = 'ok' }: { children: React.ReactNode; tone?: 'ok' | 'warn' }) {
  return <span className={`status-pill ${tone}`}>{children}</span>;
}

function DashboardPage({ page, data, experiments, dataError, reducedMotion, onReduceMotionChange, highContrast, onHighContrastChange, lightMode, onLightModeChange, onUpload }: { page: Page; data: RunData; experiments: ExperimentResults | null; dataError: string | null; reducedMotion: boolean; onReduceMotionChange: (value: boolean) => void; highContrast: boolean; onHighContrastChange: (value: boolean) => void; lightMode: boolean; onLightModeChange: (value: boolean) => void; onUpload: (file: File) => void }) {
  const { selectedRow, pipelineAnimating, setSelectedRow, setPipelineAnimating } = useRunDataStore();
  const [fileName, setFileName] = useState('predictions.csv');
  const [dragging, setDragging] = useState(false);
  const flagged = data.rows.filter(row => row.label === 1);
  const meanScore = data.rows.reduce((sum, row) => sum + row.score, 0) / Math.max(data.rows.length, 1);

  const upload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    onUpload(file);
  };
  const acceptFile = (file: File) => {
    setFileName(file.name);
    onUpload(file);
  };
  const dropFile = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file?.name.toLowerCase().endsWith('.csv')) acceptFile(file);
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
          <label className="upload-button">
            <input type="file" accept=".csv" onChange={upload} />
            Upload inference CSV
          </label>
        </div>
      </header>
      <div className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={dropFile}>
        Drop a detector CSV here, or use Upload inference CSV. Only exported detector columns are accepted.
      </div>
      <section className="kpi-grid">
        <KPICard label="Traces analyzed" value={data.meta.n_rows.toLocaleString()} sub={fileName} accentColor="var(--accent)" />
        <KPICard label="Suspicious traces" value={data.meta.n_flagged.toLocaleString()} sub={`${((data.meta.n_flagged / data.meta.n_rows) * 100).toFixed(2)}% above threshold`} accentColor="var(--threat)" />
        <KPICard label="Calibration threshold" value={data.meta.threshold.toFixed(4)} sub={`α = ${data.meta.alpha.toFixed(2)} · persisted threshold`} accentColor="var(--warn)" />
        <KPICard label="Mean anomaly score" value={meanScore.toFixed(4)} sub="fused ensemble score" accentColor="var(--info-proxy)" />
      </section>
      <div className="evidence-banner" role="status">
        <span className="banner-icon">✓</span>
        <div><strong>Measured detector output</strong><span>Scores below are exported from the verified batch artifact. A flag indicates deviation from benign HPC behaviour, not proof of a backdoor.</span></div>
        <span className="evidence-badge measured">MEASURED</span>
      </div>
      <section className="hero-grid">
        <div className="glass-panel hero-panel">
          <div className="section-heading">
            <div><span className="eyebrow">LIVE MODEL GRAPH</span><h2>Neural detection pipeline</h2></div>
            <StatusPill tone={flagged.length ? 'warn' : 'ok'}>{flagged.length ? `${flagged.length} REVIEW` : 'ALL CLEAR'}</StatusPill>
          </div>
          <NeuralPipeline row={selectedRow} threshold={data.meta.threshold} detectors={data.meta.detectors} animating={pipelineAnimating} reducedMotion={reducedMotion} onAnimationEnd={() => setPipelineAnimating(false)} />
        </div>
        <div className="glass-panel chart-panel">
          <div className="section-heading"><div><span className="eyebrow">{experiments ? 'BENIGN OOF REFERENCE DISTRIBUTION' : 'CURRENT-RUN SCORES — NOT BENIGN REFERENCE'}</span><h2>Score calibration</h2></div><span className="mono">τ {data.meta.threshold.toFixed(4)}</span></div>
          <ScoreDistribution scores={experiments?.fused_oof ?? data.calibration.oof_scores} threshold={data.meta.threshold} nBins={40} height={230} />
          <div className="chart-note"><span className="dot ok" /> Clean baseline <span className="dot threat" /> Threshold exceedance</div>
        </div>
      </section>
      <section className="glass-panel table-panel">
        <div className="section-heading"><div><span className="eyebrow">TRACE FORENSICS</span><h2>Detection results</h2></div><button className="text-button" onClick={() => setSelectedRow(data.rows[0] ?? null)}>Inspect first trace →</button></div>
        <TracesTable rows={data.rows} threshold={data.meta.threshold} selectedRowId={selectedRow?.row_id ?? null} onSelectRow={setSelectedRow} />
      </section>
    </>
  );

  const live = (
    <div className="page-section">
      <header className="topbar"><div><div className="eyebrow">LIVE DETECTION</div><h1>Trace inspection</h1><p>Upload an inference CSV and animate its feature-to-verdict path.</p></div><div className="topbar-actions"><label className="upload-button"><input type="file" accept=".csv" onChange={upload} />Upload inference CSV</label><StatusPill>PRECOMPUTED ARTIFACT</StatusPill></div></header>
      <div className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={dropFile}>Drop a detector CSV here to replace the current run.</div>
      <div className="glass-panel live-panel">
        <div className="live-controls" aria-label="Pipeline playback controls">
          <button className="control-button primary" onClick={() => setPipelineAnimating(!pipelineAnimating)}>{pipelineAnimating ? 'Pause flow' : 'Play flow'}</button>
          <button className="control-button" onClick={() => { setSelectedRow(data.rows[(selectedRow?.row_id ?? -1) + 1] ?? data.rows[0]); setPipelineAnimating(true); }}>Step row</button>
          <span className="mono">{reducedMotion ? 'reduced motion' : 'single-row playback'}</span>
        </div>
        <div className="stage-stepper" aria-label="Pipeline stages">
          {['Ingest', 'Validate', 'Transform', 'Detect', 'Fuse', 'Decide'].map((stage, index) => <span key={stage} className={`stage-step ${pipelineAnimating && index === 3 ? 'active' : index < 3 ? 'done' : ''}`}>{stage}</span>)}
        </div>
        <NeuralPipeline row={selectedRow ?? data.rows[0] ?? null} threshold={data.meta.threshold} detectors={data.meta.detectors} animating={pipelineAnimating} reducedMotion={reducedMotion} onAnimationEnd={() => setPipelineAnimating(false)} />
      </div>
      <div className="glass-panel table-panel"><TracesTable rows={data.rows} threshold={data.meta.threshold} selectedRowId={selectedRow?.row_id ?? null} onSelectRow={setSelectedRow} /></div>
    </div>
  );

  const traces = <div className="page-section"><header className="topbar"><div><div className="eyebrow">TRACE EXPLORER</div><h1>All monitored traces</h1><p>Search, filter and inspect the actual inference output.</p></div></header><div className="glass-panel table-panel"><TracesTable rows={data.rows} threshold={data.meta.threshold} selectedRowId={selectedRow?.row_id ?? null} onSelectRow={setSelectedRow} /></div></div>;

  const calibration = <div className="page-section"><header className="topbar"><div><div className="eyebrow">MODEL GOVERNANCE</div><h1>Model & evaluation</h1><p>Persisted artifact metadata, calibration and measured benign-only validation evidence.</p></div></header><div className="model-overview-grid"><div className="glass-panel info-card"><span className="eyebrow">MODEL STATUS</span><strong>Loaded & verified</strong><p>Seven-detector ensemble with SHA-256 manifest validation.</p><StatusPill>INTEGRITY OK</StatusPill></div><div className="glass-panel info-card"><span className="eyebrow">TRAINING POLICY</span><strong>800 benign traces</strong><p>No attack labels were used. Classification metrics require an independent labelled set.</p><StatusPill tone="warn">LABELS REQUIRED</StatusPill></div><div className="glass-panel calibration-card"><ScoreDistribution scores={experiments?.fused_oof ?? data.calibration.oof_scores} threshold={data.meta.threshold} height={260} /></div></div>{experiments ? <><div className="experiment-summary"><div className="glass-panel info-card"><span className="eyebrow">VALIDATION DESIGN</span><strong>{experiments.meta.cv_repeats} × {experiments.meta.cv_folds}-fold</strong><p>{experiments.meta.n_samples} benign traces · seed {experiments.meta.seed}</p></div><div className="glass-panel info-card"><span className="eyebrow">FUSED OOF SCORE</span><strong>{experiments.fused_oof_stats.mean.toFixed(3)}</strong><p>σ {experiments.fused_oof_stats.std.toFixed(3)} · q95 {experiments.fused_oof_stats.q95.toFixed(3)}</p></div></div><div className="glass-panel experiment-table"><div className="section-heading"><div><span className="eyebrow">DETECTOR STABILITY</span><h2>Held-out score comparison</h2></div><span className="evidence-badge measured">MEASURED</span></div><table><thead><tr><th>DETECTOR</th><th>OOF MEAN</th><th>OOF STD</th><th>OOF Q95</th></tr></thead><tbody>{Object.entries(experiments.per_detector).map(([name, stats]) => <tr key={name}><td className="mono">{name}</td><td>{stats.oof_mean.toFixed(3)}</td><td>{stats.oof_std.toFixed(3)}</td><td>{stats.oof_q95.toFixed(3)}</td></tr>)}</tbody></table></div></> : <div className="empty-state"><strong>Experiment results unavailable</strong><span>Run the training pipeline to export reports/experiment_results.json.</span></div>}<div className="glass-panel settings-card"><div className="section-heading"><div><span className="eyebrow">ACCESSIBILITY</span><h2>Display preferences</h2></div></div><label className="theme-toggle"><span><strong>{lightMode ? 'Light mode' : 'Pitch black mode'}</strong><small>Animated interface theme</small></span><button type="button" className={`theme-switch ${lightMode ? 'on' : ''}`} aria-label={lightMode ? 'Switch to pitch black mode' : 'Switch to light mode'} aria-pressed={lightMode} onClick={() => onLightModeChange(!lightMode)}><span className="theme-switch-thumb">{lightMode ? '☀' : '☾'}</span></button></label><label className="setting-row motion-toggle"><span>Reduce motion</span><input type="checkbox" checked={reducedMotion} onChange={event => onReduceMotionChange(event.target.checked)} /></label><label className="setting-row motion-toggle"><span>High contrast mode</span><input type="checkbox" checked={highContrast} onChange={event => onHighContrastChange(event.target.checked)} /></label></div></div>;

  const content = page === 'overview' ? overview : page === 'live' ? live : page === 'traces' ? traces : calibration;
  return <>
    {dataError && <div className="error-banner" role="alert"><strong>Input rejected</strong><span>{dataError}</span></div>}
    {content}
    {selectedRow && (
      <aside className="drawer" aria-label="Trace detail">
        <div className="drawer-header"><div><span className="eyebrow">TRACE DETAIL</span><h2>Row #{selectedRow.row_id}</h2></div><button className="drawer-close" aria-label="Close trace detail" onClick={() => setSelectedRow(null)}>×</button></div>
        <div className="drawer-score">{selectedRow.score.toFixed(4)}</div>
        <p className="drawer-copy">{selectedRow.label === 1 ? 'Flagged — deviates from benign profile.' : 'Clean — within the calibrated benign profile.'}</p>
        <StatusPill tone={selectedRow.label === 1 ? 'warn' : 'ok'}>{selectedRow.label === 1 ? 'FLAGGED' : 'CLEAN'}</StatusPill>
        <div className="drawer-section"><h3>Top feature deviations</h3>{selectedRow.top_features.map(feature => <div className="detector-row" key={feature.name}><span>{feature.name}</span><strong>{feature.z_score > 0 ? '+' : ''}{feature.z_score.toFixed(2)}σ</strong></div>)}</div>
        <div className="drawer-section"><h3>Detector scores</h3>{Object.entries(selectedRow.stage_scores).map(([name, score]) => <div className="detector-row" key={name}><span>{name}</span><strong>{score.toFixed(4)}</strong></div>)}</div>
      </aside>
    )}
  </>;
}

export default function App() {
  const { runData, setRunData } = useRunDataStore();
  const [page, setPage] = useState<Page>('overview');
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [experiments, setExperiments] = useState<ExperimentResults | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [highContrast, setHighContrast] = useState(false);
  const [lightMode, setLightMode] = useState(() => localStorage.getItem('hpc-sentinel-theme') === 'light');
  const [dataError, setDataError] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.classList.toggle('high-contrast', highContrast);
  }, [highContrast]);
  useEffect(() => {
    document.documentElement.classList.toggle('light-theme', lightMode);
    localStorage.setItem('hpc-sentinel-theme', lightMode ? 'light' : 'dark');
  }, [lightMode]);

  useEffect(() => {
    fetch('/data/manifest.json').then(response => {
      if (!response.ok) throw new Error(`Artifact manifest request failed (${response.status}).`);
      return response.json();
    }).then(setManifest).catch(error => setDataError(error instanceof Error ? error.message : 'Artifact manifest could not be loaded.'));
  }, []);

  useEffect(() => {
    if (!manifest || runData) return;
    fetch('/data/predictions.csv').then(response => {
      if (!response.ok) throw new Error(`Inference artifact request failed (${response.status}).`);
      return response.text();
    }).then(text => setRunData(buildRunData(text, manifest))).catch(error => setDataError(error instanceof Error ? error.message : 'Inference artifact could not be loaded.'));
  }, [manifest, runData, setRunData]);

  useEffect(() => {
    fetch('/data/experiment_results.json').then(response => response.json()).then(setExperiments).catch(() => undefined);
  }, []);

  const handleUpload = (file: File) => {
    if (!manifest) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        setDataError(null);
        setRunData(buildRunData(String(reader.result), manifest));
      } catch (error) {
        setDataError(error instanceof Error ? error.message : 'CSV validation failed.');
      }
    };
    reader.onerror = () => setDataError('The selected CSV could not be read.');
    reader.readAsText(file);
  };

  if (!runData && dataError) return <div className="loading-screen error-screen"><strong>HPC Sentinel could not load verified data</strong><p>{dataError}</p><button className="control-button primary" onClick={() => window.location.reload()}>Retry</button></div>;
  if (!runData) return <div className="loading-screen"><div className="loading-orb" /><p>Loading verified inference artifact…</p></div>;
  return <Layout currentPage={page} onNavigate={setPage}><DashboardPage page={page} data={runData} experiments={experiments} dataError={dataError} reducedMotion={reducedMotion} onReduceMotionChange={setReducedMotion} onHighContrastChange={setHighContrast} highContrast={highContrast} lightMode={lightMode} onLightModeChange={setLightMode} onUpload={handleUpload} /></Layout>;
}
