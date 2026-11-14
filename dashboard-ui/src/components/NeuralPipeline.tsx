import { useEffect, useRef, useCallback } from 'react';
import s from './NeuralPipeline.module.css';
import type { TraceRow } from '../types/runData';

interface NeuralPipelineProps {
  row: TraceRow | null;
  threshold: number;
  detectors: string[];
  animating: boolean;
  onAnimationEnd?: () => void;
  reducedMotion?: boolean;
}

interface NodeDef {
  id: string;
  x: number;
  y: number;
  r: number;
  color: string;
  label: string;
  score?: number;
}

interface EdgeDef {
  from: string;
  to: string;
}

interface Particle {
  edge: EdgeDef;
  t: number;      // 0..1 along edge
  speed: number;
  alpha: number;
}

const HPC_COUNTERS = ['cache-ref', 'cycles', 'LLC-loads'];
const TRANSFORMS = ['log1p', 'scale', 'ratio'];
const DETECTOR_NAMES = ['Mahal', 'PCA', 'IForest', 'kNN', 'GMM', 'OCSVM', 'ECOD'];

function lerp(a: number, b: number, t: number) { return a + (b - a) * t; }
function clamp(v: number, lo: number, hi: number) { return Math.max(lo, Math.min(hi, v)); }

function scoreToColor(score: number): string {
  // 0 = ok/green, 1 = threat/red, interpolated
  const r = Math.round(lerp(52, 255, score));
  const g = Math.round(lerp(211, 92, score));
  const b = Math.round(lerp(153, 122, score));
  return `rgb(${r},${g},${b})`;
}

function zScoreToColor(z: number): string {
  if (z > 0) {
    // Positive deviation: orange/red
    const t = clamp(Math.abs(z) / 4, 0, 1);
    const r = Math.round(lerp(245, 255, t));
    const g = Math.round(lerp(181, 60, t));
    const b = Math.round(lerp(68, 50, t));
    return `rgb(${r},${g},${b})`;
  } else {
    // Negative deviation: blue
    const t = clamp(Math.abs(z) / 4, 0, 1);
    const r = Math.round(lerp(91, 30, t));
    const g = Math.round(lerp(140, 80, t));
    const b = Math.round(lerp(255, 255, t));
    return `rgb(${r},${g},${b})`;
  }

}

function withAlpha(color: string, alpha: number): string {
  const match = color.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)$/);
  return match ? `rgba(${match[1]},${match[2]},${match[3]},${alpha})` : color;
}

function scoreToRank(score: number): number {
  return clamp(1 - Math.exp(-Math.max(score, 0)), 0, 1);
}

export default function NeuralPipeline({ row, threshold, detectors, animating, onAnimationEnd, reducedMotion = false }: NeuralPipelineProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const rafRef = useRef<number>(0);
  const phaseRef = useRef<number>(0);       // 0 = idle, 1 = propagating, 2 = done
  const timeRef = useRef<number>(0);

  // Build layout
  const W = 820, H = 280;
  const COL_INPUT = 60;
  const COL_TRANSFORM = 210;
  const COL_DETECTOR = 400;
  const COL_FUSION = 620;
  const COL_VERDICT = 760;

  const buildNodes = useCallback((row: TraceRow | null): NodeDef[] => {
    const nodes: NodeDef[] = [];

    // Input nodes (HPC counters)
    HPC_COUNTERS.forEach((name, i) => {
      const feat = row?.top_features.find(f => f.name.includes(name.split('-')[0]));
      const z = feat?.z_score ?? 0;
      const absZ = Math.min(Math.abs(z), 5);
      const r = 10 + absZ * 2.5;
      nodes.push({
        id: `input_${i}`,
        x: COL_INPUT,
        y: 60 + i * 80,
        r,
        color: row ? zScoreToColor(z) : 'rgba(91,140,255,0.5)',
        label: name,
        score: row ? clamp(absZ / 5, 0, 1) : 0.3,
      });
    });

    // Transform nodes
    TRANSFORMS.forEach((name, i) => {
      nodes.push({
        id: `transform_${i}`,
        x: COL_TRANSFORM,
        y: 70 + i * 70,
        r: 12,
        color: 'rgba(167,139,250,0.8)',
        label: name,
        score: 0.5,
      });
    });

    // Detector nodes
    const detNames = detectors.length > 0 ? detectors : DETECTOR_NAMES;
    detNames.forEach((name, i) => {
      const shortName = DETECTOR_NAMES[i] ?? name.slice(0, 6);
      const detScore = row?.stage_scores[name] ?? 0;
      const displayDetScore = scoreToRank(detScore);
      nodes.push({
        id: `det_${i}`,
        x: COL_DETECTOR,
        y: 30 + i * 38,
        r: 10 + displayDetScore * 8,
        color: scoreToColor(displayDetScore),
        label: shortName,
        score: displayDetScore,
      });
    });

    // Fusion node
    const fusedScore = row?.score ?? 0;
    const displayFusedScore = scoreToRank(fusedScore);
    nodes.push({
      id: 'fusion',
      x: COL_FUSION,
      y: H / 2,
      r: 22,
      color: scoreToColor(displayFusedScore),
      label: 'fused',
      score: displayFusedScore,
    });

    // Verdict node
    const isFlagged = (row?.label ?? 0) === 1;
    nodes.push({
      id: 'verdict',
      x: COL_VERDICT,
      y: H / 2,
      r: 20,
      color: isFlagged ? 'var(--threat)' : 'var(--ok)',
      label: isFlagged ? 'FLAGGED' : 'CLEAN',
      score: isFlagged ? 1 : 0,
    });

    return nodes;
  }, [detectors]);

  const buildEdges = useCallback((): EdgeDef[] => {
    const edges: EdgeDef[] = [];
    const detCount = detectors.length || DETECTOR_NAMES.length;

    // Input → Transform (all to all)
    HPC_COUNTERS.forEach((_, i) => {
      TRANSFORMS.forEach((_, j) => {
        edges.push({ from: `input_${i}`, to: `transform_${j}` });
      });
    });

    // Transform → Detectors (each transform to some detectors)
    TRANSFORMS.forEach((_, j) => {
      for (let d = 0; d < detCount; d++) {
        if ((j + d) % 2 === 0 || d === j) {
          edges.push({ from: `transform_${j}`, to: `det_${d}` });
        }
      }
    });

    // All detectors → fusion
    for (let d = 0; d < detCount; d++) {
      edges.push({ from: `det_${d}`, to: 'fusion' });
    }

    // Fusion → Verdict
    edges.push({ from: 'fusion', to: 'verdict' });

    return edges;
  }, [detectors]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    if (!ctx) return;

    const nodes = buildNodes(row);
    const edges = buildEdges();
    const nodeMap = new Map<string, NodeDef>(nodes.map(n => [n.id, n]));

    if (animating) {
      phaseRef.current = 1;
      timeRef.current = 0;
      // Spawn particles
      particlesRef.current = edges.map(edge => ({
        edge,
        t: Math.random() * 0.5,
        speed: 0.004 + (row?.score ?? 0.3) * 0.008 + Math.random() * 0.003,
        alpha: 0.6 + Math.random() * 0.4,
      }));
    }

    const prefersReduced = reducedMotion || window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function drawGlowCircle(
      ctx: CanvasRenderingContext2D,
      x: number, y: number, r: number,
      fillColor: string, glowColor: string, glowRadius: number
    ) {
      // Glow
      const grd = ctx.createRadialGradient(x, y, r * 0.2, x, y, glowRadius);
      grd.addColorStop(0, withAlpha(glowColor, 0.35));
      grd.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.beginPath();
      ctx.arc(x, y, glowRadius, 0, Math.PI * 2);
      ctx.fillStyle = grd;
      ctx.fill();

      // Fill
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = fillColor;
      ctx.fill();

      // Ring
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.strokeStyle = withAlpha(fillColor, 0.9);
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    function drawGauge(
      ctx: CanvasRenderingContext2D,
      x: number, y: number, r: number,
      score: number, threshold: number, t: number
    ) {
      const displayScore = prefersReduced ? score : score * Math.min(1, t * 2);
      const startAngle = -Math.PI * 0.75;
      const endAngle = Math.PI * 0.75;
      const scoreAngle = startAngle + (endAngle - startAngle) * displayScore;
      const threshAngle = startAngle + (endAngle - startAngle) * threshold;

      // Background arc
      ctx.beginPath();
      ctx.arc(x, y, r, startAngle, endAngle);
      ctx.strokeStyle = 'rgba(255,255,255,0.1)';
      ctx.lineWidth = 4;
      ctx.lineCap = 'round';
      ctx.stroke();

      // Score arc
      const c = scoreToColor(displayScore);
      ctx.beginPath();
      ctx.arc(x, y, r, startAngle, scoreAngle);
      ctx.strokeStyle = c;
      ctx.lineWidth = 4;
      ctx.stroke();

      // Threshold marker
      const tx2 = x + (r + 4) * Math.cos(threshAngle);
      const ty2 = y + (r + 4) * Math.sin(threshAngle);
      ctx.beginPath();
      ctx.arc(tx2, ty2, 3, 0, Math.PI * 2);
      ctx.fillStyle = 'rgb(255,92,122)';
      ctx.fill();

      // Center score text
      ctx.fillStyle = c;
      ctx.font = `bold 9px JetBrains Mono, monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(displayScore.toFixed(2), x, y);
    }

    function drawArrow(ctx: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number, alpha: number) {
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = 'rgba(91,140,255,0.3)';
      ctx.lineWidth = 0.8;
      ctx.stroke();
      ctx.restore();
    }

    function drawLabel(ctx: CanvasRenderingContext2D, x: number, y: number, text: string, color: string) {
      ctx.save();
      ctx.fillStyle = color;
      ctx.font = `10px Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(text, x, y);
      ctx.restore();
    }

    let lastTime = performance.now();

    function render(now: number) {
      const dt = (now - lastTime) / 1000;
      lastTime = now;
      timeRef.current += dt;
      const t = timeRef.current;

      if (t > 1 && phaseRef.current === 1) {
        phaseRef.current = 2;
        onAnimationEnd?.();
      }

      ctx.clearRect(0, 0, W, H);

      // Draw column section backgrounds
      const sections = [
        { x: 10, w: 100, label: 'HPC COUNTERS' },
        { x: 165, w: 100, label: 'TRANSFORMS' },
        { x: 340, w: 130, label: 'DETECTORS' },
        { x: 580, w: 80, label: 'FUSION' },
        { x: 720, w: 80, label: 'VERDICT' },
      ];
      sections.forEach(sec => {
        ctx.fillStyle = 'rgba(255,255,255,0.02)';
        roundRect(ctx, sec.x, 4, sec.w, H - 8, 8);
        ctx.fill();
        ctx.fillStyle = 'rgba(170,180,204,0.3)';
        ctx.font = '7px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(sec.label, sec.x + sec.w / 2, 10);
      });

      // Draw edges
      edges.forEach(edge => {
        const from = nodeMap.get(edge.from);
        const to = nodeMap.get(edge.to);
        if (!from || !to) return;
        const edgeAlpha = row ? 0.25 : 0.12;
        drawArrow(ctx, from.x, from.y, to.x, to.y, edgeAlpha);
      });

      // Draw particles
      if (!prefersReduced) {
        particlesRef.current.forEach(p => {
          const from = nodeMap.get(p.edge.from);
          const to = nodeMap.get(p.edge.to);
          if (!from || !to) return;
          const px = lerp(from.x, to.x, p.t);
          const py = lerp(from.y, to.y, p.t);
          ctx.beginPath();
          ctx.arc(px, py, 2, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(91,140,255,${p.alpha * (1 - Math.abs(p.t - 0.5) * 0.5)})`;
          ctx.fill();
        });
      }

      // Draw nodes
      nodes.forEach(node => {
        if (!nodeMap.has(node.id)) return;
        const isVerdictNode = node.id === 'verdict';
        const isFusionNode = node.id === 'fusion';

        // Verdict: pulse
        if (isVerdictNode && row && !prefersReduced) {
          const isFlagged = row.label === 1;
          if (isFlagged) {
            const pulseR = node.r + Math.sin(t * 6) * 5 * Math.min(1, t);
            ctx.beginPath();
            ctx.arc(node.x, node.y, pulseR, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(255,92,122,0.3)';
            ctx.lineWidth = 2;
            ctx.stroke();
          }
        }

        // Fusion: ring gauge
        if (isFusionNode) {
          drawGauge(ctx, node.x, node.y, node.r + 8, node.score ?? 0, scoreToRank(threshold), t);
        } else {
          // Entrance animation: nodes appear in waves
          const col = node.id.startsWith('input') ? 0
            : node.id.startsWith('transform') ? 1
            : node.id.startsWith('det') ? 2
            : node.id === 'fusion' ? 3 : 4;
          const delay = col * 0.3;
          const alpha = prefersReduced ? 1 : clamp((t - delay) / 0.4, 0, 1);

          ctx.save();
          ctx.globalAlpha = alpha;
          const colorRgb = node.color.startsWith('var(') ? (
            node.color === 'var(--ok)' ? 'rgb(52,211,153)' : 'rgb(255,92,122)'
          ) : node.color;

          drawGlowCircle(ctx, node.x, node.y, node.r, colorRgb, colorRgb, node.r * 2.5);
          ctx.restore();
        }

        // Label
        const labelY = node.y + node.r + 6;
        const labelColor = node.id === 'verdict'
          ? (row?.label === 1 ? 'rgba(255,92,122,0.9)' : 'rgba(52,211,153,0.9)')
          : 'rgba(170,180,204,0.8)';
        drawLabel(ctx, node.x, labelY, node.label, labelColor);
      });

      // Advance particles
      particlesRef.current = particlesRef.current.map(p => ({
        ...p,
        t: p.t + p.speed,
      })).filter(p => p.t < 1.0);

      // Respawn
      if (animating && !prefersReduced) {
        edges.forEach(edge => {
          if (Math.random() < 0.04) {
            particlesRef.current.push({
              edge,
              t: 0,
              speed: 0.004 + (row?.score ?? 0.3) * 0.008 + Math.random() * 0.004,
              alpha: 0.5 + Math.random() * 0.5,
            });
          }
        });
      }

      rafRef.current = requestAnimationFrame(render);
    }

    rafRef.current = requestAnimationFrame(render);
    return () => cancelAnimationFrame(rafRef.current);
  }, [row, threshold, animating, buildNodes, buildEdges, detectors, onAnimationEnd, reducedMotion]);

  return (
    <div className={s.wrap}>
      <div className={s.header}>
        <div>
          <div className={s.title}>Neural Detection Pipeline</div>
          <div className={s.subtitle}>
            {row ? `Row #${row.row_id} · Score ${row.score.toFixed(4)}` : 'Select a trace row to animate'}
          </div>
        </div>
      </div>

      {!row ? (
        <div className={s.noData}>
          <div className={s.noDataIcon}>◈</div>
          <span>Select a row in the Traces table to visualize the pipeline</span>
        </div>
      ) : (
        <>
          <canvas
            ref={canvasRef}
            width={W}
            height={H}
            className={s.canvas}
          />
          <div className={s.legend}>
            <div className={s.legendItem}>
              <div className={s.legendDot} style={{ background: 'var(--ok)' }} />
              <span>Low anomaly</span>
            </div>
            <div className={s.legendItem}>
              <div className={s.legendDot} style={{ background: 'var(--threat)' }} />
              <span>High anomaly</span>
            </div>
            <div className={s.legendItem}>
              <div className={s.legendDot} style={{ background: 'var(--info-proxy)' }} />
              <span>Transform</span>
            </div>
            <div className={s.legendItem}>
              <div className={s.legendDot} style={{ background: 'var(--accent)' }} />
              <span>Particle flow</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}
