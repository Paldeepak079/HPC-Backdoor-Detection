import { useState, useMemo } from 'react';
import s from './TracesTable.module.css';
import type { TraceRow } from '../types/runData';

interface TracesTableProps {
  rows: TraceRow[];
  threshold: number;
  selectedRowId: number | null;
  onSelectRow: (row: TraceRow) => void;
}

type SortKey = 'row_id' | 'score';
type SortDir = 'asc' | 'desc';
type Filter = 'all' | 'clean' | 'flagged';

const PAGE_SIZE = 25;

export default function TracesTable({ rows, threshold, selectedRowId, onSelectRow }: TracesTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('row_id');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir(key === 'score' ? 'desc' : 'asc');
    }
    setPage(0);
  };

  const filtered = useMemo(() => {
    let r = rows;
    if (filter === 'clean') r = r.filter(x => x.label === 0);
    if (filter === 'flagged') r = r.filter(x => x.label === 1);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      r = r.filter(x => x.row_id.toString().includes(q) || x.score.toFixed(4).includes(q));
    }
    return r;
  }, [rows, filter, search]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const mult = sortDir === 'asc' ? 1 : -1;
      if (sortKey === 'score') return (a.score - b.score) * mult;
      return (a.row_id - b.row_id) * mult;
    });
  }, [filtered, sortKey, sortDir]);

  const pageRows = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);

  function scoreColor(score: number) {
    if (score >= threshold) return 'var(--threat)';
    if (score >= threshold * 0.7) return 'var(--warn)';
    return 'var(--ok)';
  }

  return (
    <div className={s.wrap}>
      <div className={s.header}>
        <span className={s.title}>Traces — {sorted.length} rows</span>
        <div className={s.controls}>
          <input
            className={s.searchBox}
            placeholder="Search row_id or score…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(0); }}
          />
          {(['all', 'clean', 'flagged'] as Filter[]).map(f => (
            <button
              key={f}
              className={`${s.filterBtn} ${filter === f ? s.active : ''}`}
              onClick={() => { setFilter(f); setPage(0); }}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className={s.tableWrap}>
        <table>
          <thead>
            <tr>
              <th
                className={`${s.sortable} ${sortKey === 'row_id' ? s.sortActive : ''}`}
                onClick={() => handleSort('row_id')}
              >
                ROW_ID {sortKey === 'row_id' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
              </th>
              <th
                className={`${s.sortable} ${sortKey === 'score' ? s.sortActive : ''}`}
                onClick={() => handleSort('score')}
              >
                SCORE {sortKey === 'score' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
              </th>
              <th>LABEL</th>
              <th>TOP FEATURES</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map(row => (
              <tr
                key={row.row_id}
                className={selectedRowId === row.row_id ? s.selected : ''}
                onClick={() => onSelectRow(row)}
              >
                <td><span className={s.rowId}>#{row.row_id.toString().padStart(4, '0')}</span></td>
                <td>
                  <div className={s.scoreCell}>
                    <span className={s.scoreVal} style={{ color: scoreColor(row.score) }}>
                      {row.score.toFixed(4)}
                    </span>
                    <div className={s.scoreBar}>
                      <div
                        className={s.scoreBarFill}
                        style={{
                          width: `${Math.min(100, (row.score / Math.max(threshold, 1)) * 100)}%`,
                          background: `linear-gradient(90deg, var(--ok), ${scoreColor(row.score)})`,
                        }}
                      />
                    </div>
                  </div>
                </td>
                <td>
                  <span className={`${s.labelChip} ${row.label === 1 ? s.flagged : s.clean}`}>
                    {row.label === 1 ? 'FLAGGED' : 'CLEAN'}
                  </span>
                </td>
                <td>
                  <div className={s.featureList}>
                    {row.top_features.slice(0, 3).map(f => (
                      <span
                        key={f.name}
                        className={`${s.featureTag} ${f.direction === 'high' ? s.high : s.low}`}
                      >
                        {f.name} {f.z_score > 0 ? '+' : ''}{f.z_score.toFixed(1)}σ
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={s.pagination}>
        <span>
          Page {page + 1} of {totalPages} · {sorted.length} total
        </span>
        <div className={s.pageButtons}>
          <button className={s.pageBtn} onClick={() => setPage(0)} disabled={page === 0}>«</button>
          <button className={s.pageBtn} onClick={() => setPage(p => p - 1)} disabled={page === 0}>‹</button>
          <button className={s.pageBtn} onClick={() => setPage(p => p + 1)} disabled={page >= totalPages - 1}>›</button>
          <button className={s.pageBtn} onClick={() => setPage(totalPages - 1)} disabled={page >= totalPages - 1}>»</button>
        </div>
      </div>
    </div>
  );
}
