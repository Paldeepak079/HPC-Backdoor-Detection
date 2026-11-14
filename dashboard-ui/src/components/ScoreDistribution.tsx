import { useState, useRef, useCallback } from 'react';
import s from './ScoreDistribution.module.css';

interface ScoreDistributionProps {
  scores: number[];
  threshold: number;
  height?: number;
  nBins?: number;
}

interface TooltipState {
  x: number;
  y: number;
  content: string;
  visible: boolean;
}

export default function ScoreDistribution({
  scores,
  threshold,
  height = 180,
  nBins = 50,
}: ScoreDistributionProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [tooltip, setTooltip] = useState<TooltipState>({ x: 0, y: 0, content: '', visible: false });

  const W = 100; // viewBox units
  const H = height;
  const PAD = { top: 8, right: 4, bottom: 24, left: 32 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  // Build histogram
  const bins: number[] = new Array(nBins).fill(0);
  scores.forEach(s => {
    const idx = Math.min(nBins - 1, Math.floor(s * nBins));
    bins[idx]++;
  });
  const maxCount = Math.max(...bins, 1);

  const threshBin = threshold * nBins;

  // Convert bin index to x pixel
  const bx = (i: number) => PAD.left + (i / nBins) * plotW;
  const bw = plotW / nBins;

  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const relX = (e.clientX - rect.left) / rect.width * W;
    const score = Math.max(0, Math.min(1, (relX - PAD.left) / plotW));
    const binIdx = Math.floor(score * nBins);
    const count = bins[Math.max(0, Math.min(nBins - 1, binIdx))] ?? 0;
    setTooltip({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      content: `score ≈ ${score.toFixed(2)} · ${count} samples`,
      visible: true,
    });
  }, [bins, nBins, plotW]);

  const handleMouseLeave = useCallback(() => {
    setTooltip(t => ({ ...t, visible: false }));
  }, []);

  return (
    <div className={s.wrap}>
      <div className={s.title}>Score Distribution</div>
      <div className={s.svgWrap}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          style={{ width: '100%', height: H, display: 'block', cursor: 'crosshair' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* Y axis */}
          <line
            x1={PAD.left} y1={PAD.top}
            x2={PAD.left} y2={PAD.top + plotH}
            stroke="rgba(255,255,255,0.1)" strokeWidth="0.5"
          />
          {/* X axis */}
          <line
            x1={PAD.left} y1={PAD.top + plotH}
            x2={PAD.left + plotW} y2={PAD.top + plotH}
            stroke="rgba(255,255,255,0.1)" strokeWidth="0.5"
          />

          {/* Bars */}
          {bins.map((count, i) => {
            const barH = (count / maxCount) * plotH;
            const x = bx(i);
            const y = PAD.top + plotH - barH;
            const isBelowThresh = i < threshBin;
            const color = isBelowThresh ? 'rgba(52,211,153,0.7)' : 'rgba(255,92,122,0.8)';
            return (
              <rect
                key={i}
                x={x}
                y={y}
                width={Math.max(bw - 0.3, 0.5)}
                height={barH}
                fill={color}
              />
            );
          })}

          {/* Threshold line */}
          {(() => {
            const tx = PAD.left + threshold * plotW;
            return (
              <g>
                <line
                  x1={tx} y1={PAD.top}
                  x2={tx} y2={PAD.top + plotH}
                  stroke="var(--threat)"
                  strokeWidth="1"
                  strokeDasharray="3,2"
                />
                <text
                  x={tx + 1} y={PAD.top + 8}
                  fill="var(--threat)"
                  fontSize="4"
                  fontFamily="JetBrains Mono, monospace"
                >
                  τ={threshold.toFixed(2)}
                </text>
              </g>
            );
          })()}

          {/* X axis labels */}
          {[0, 0.25, 0.5, 0.75, 1.0].map(v => (
            <text
              key={v}
              x={PAD.left + v * plotW}
              y={PAD.top + plotH + 10}
              fill="rgba(170,180,204,0.6)"
              fontSize="4"
              textAnchor="middle"
              fontFamily="JetBrains Mono, monospace"
            >
              {v.toFixed(2)}
            </text>
          ))}
        </svg>

        {tooltip.visible && (
          <div
            className={s.tooltip}
            style={{ left: tooltip.x, top: tooltip.y }}
          >
            {tooltip.content}
          </div>
        )}
      </div>

      <div className={s.legend}>
        <div className={s.legendItem}>
          <div className={s.legendDot} style={{ background: 'var(--ok)' }} />
          <span>Below τ (clean)</span>
        </div>
        <div className={s.legendItem}>
          <div className={s.legendDot} style={{ background: 'var(--threat)' }} />
          <span>Above τ (flagged)</span>
        </div>
        <div className={s.legendItem}>
          <div className={s.legendDot} style={{ background: 'var(--threat)', borderRadius: 0 }} />
          <span>τ = {threshold.toFixed(3)}</span>
        </div>
      </div>
    </div>
  );
}
