import type { RunData, TraceRow, Calibration } from '../types/runData';

const DETECTORS = ['Mahalanobis', 'PCA', 'IForest', 'kNN', 'GMM', 'OCSVM'];
const FEATURES = ['cache-references', 'cycles', 'LLC-loads'];

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return ((s >>> 0) / 0xffffffff);
  };
}

function generateRows(rng: () => number, nRows: number, tau: number): TraceRow[] {
  const rows: TraceRow[] = [];

  for (let i = 0; i < nRows; i++) {
    // ~5% flagged
    const isAnomalous = i < 40 || rng() < 0.005;

    // Generate detector scores
    const stageScores: Record<string, number> = {};
    for (const det of DETECTORS) {
      if (isAnomalous) {
        stageScores[det] = 0.55 + rng() * 0.44;
      } else {
        stageScores[det] = rng() * 0.45;
      }
    }

    // Fused score (mean of detector scores with noise)
    const meanScore = DETECTORS.reduce((s, d) => s + stageScores[d], 0) / DETECTORS.length;
    const score = Math.min(1, Math.max(0, meanScore + (rng() - 0.5) * 0.08));
    const label: 0 | 1 = score >= tau ? 1 : 0;

    // Generate top features
    const featureZScores = FEATURES.map(name => {
      const z = isAnomalous
        ? (rng() * 5 + 1) * (rng() > 0.5 ? 1 : -1)
        : (rng() * 2 - 1);
      return { name, z_score: z, direction: (z >= 0 ? 'high' : 'low') as 'high' | 'low' };
    });
    featureZScores.sort((a, b) => Math.abs(b.z_score) - Math.abs(a.z_score));

    rows.push({
      row_id: i,
      score,
      label,
      top_features: featureZScores,
      stage_scores: stageScores,
    });
  }

  return rows;
}

function generateOofScores(rng: () => number, n: number, tau: number): number[] {
  const scores: number[] = [];
  for (let i = 0; i < n; i++) {
    // Beta-like: most benign near 0, a tail up to tau+
    const u = rng();
    if (rng() < 0.05) {
      scores.push(0.55 + rng() * 0.44);
    } else {
      scores.push(u * u * 0.75);
    }
  }
  return scores;
}

const rng = seededRandom(42);
const TAU = 0.62;
const rows = generateRows(rng, 800, TAU);
const oofScores = generateOofScores(rng, 800, TAU);
const fprCount = oofScores.filter(s => s >= TAU).length;
const oof_fpr = fprCount / oofScores.length;

export const sampleRunData: RunData = {
  meta: {
    timestamp: '2024-07-14T03:14:15Z',
    n_rows: 800,
    n_flagged: rows.filter(r => r.label === 1).length,
    threshold: TAU,
    alpha: 0.05,
    detectors: DETECTORS,
    config_hash: 'a3f9c812b4',
  },
  rows,
  calibration: {
    oof_scores: oofScores,
    oof_fpr_at_alpha: parseFloat(oof_fpr.toFixed(4)),
    alpha: 0.05,
    tau: TAU,
  },
};
