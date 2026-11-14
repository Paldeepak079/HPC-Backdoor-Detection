import s from './KPICard.module.css';

type EvidenceType = 'measured' | 'synthetic' | 'hypothesis';

interface KPICardProps {
  label: string;
  value: string | number;
  sub?: string;
  evidence?: EvidenceType;
  accentColor?: string;
}

const EVIDENCE_LABEL: Record<EvidenceType, string> = {
  measured: 'MEASURED',
  synthetic: 'SYNTHETIC PROXY',
  hypothesis: 'HYPOTHESIS',
};

export default function KPICard({ label, value, sub, evidence = 'measured', accentColor }: KPICardProps) {
  return (
    <div className={s.card}>
      {accentColor && (
        <div
          className={s.accentLine}
          style={{ background: `linear-gradient(90deg, ${accentColor}, transparent)` }}
        />
      )}
      <span className={s.label}>{label}</span>
      <div className={s.valueRow}>
        <span className={s.value}>{value}</span>
      </div>
      {sub && <span className={s.sub}>{sub}</span>}
      <span className={`${s.badge} ${s[evidence]}`}>
        {EVIDENCE_LABEL[evidence]}
      </span>
    </div>
  );
}
