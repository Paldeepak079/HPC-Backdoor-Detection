import React, { useState } from 'react';
import s from './Layout.module.css';
import { useRunDataStore } from '../store/runData';

export type Page = 'overview' | 'live' | 'traces' | 'calibration' | 'settings';

interface NavItemDef {
  id: Page;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItemDef[] = [
  { id: 'overview',    label: 'Overview',         icon: '⬡' },
  { id: 'live',        label: 'Live Analysis',     icon: '◈' },
  { id: 'traces',      label: 'Traces',            icon: '≡' },
  { id: 'calibration', label: 'Model & Calibration', icon: '◎' },
  { id: 'settings',    label: 'Settings',          icon: '⚙' },
];

interface LayoutProps {
  currentPage: Page;
  onNavigate: (page: Page) => void;
  children: React.ReactNode;
}

export default function Layout({ currentPage, onNavigate, children }: LayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  const isSampleData = useRunDataStore(s => s.isSampleData);

  return (
    <div className={s.layout}>
      <div className={`bg-blobs`} />

      <aside className={`${s.sidebar} ${collapsed ? s.collapsed : ''}`}>
        <div className={s.logoArea}>
          <div className={s.logoIcon}>🛡</div>
          <div className={s.logoText}>
            <span className={s.name}>HPC Sentinel</span>
            <span className={s.sub}>Backdoor Detector</span>
          </div>
        </div>

        <nav className={s.nav}>
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              className={`${s.navItem} ${currentPage === item.id ? s.active : ''}`}
              onClick={() => onNavigate(item.id)}
              title={collapsed ? item.label : undefined}
            >
              <span className={s.navIcon}>{item.icon}</span>
              <span className={s.navLabel}>{item.label}</span>
            </button>
          ))}
        </nav>

        {isSampleData && (
          <div className={s.sampleBadge}>
            SAMPLE DATA<br />NOT A RESULT
          </div>
        )}

        <div className={s.sidebarFooter}>
          <button
            className={s.collapseBtn}
            onClick={() => setCollapsed(c => !c)}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? '›' : '‹'}
          </button>
        </div>
      </aside>

      <main className={s.main}>
        <div className={s.pageWrapper} key={currentPage}>
          {children}
        </div>
      </main>
    </div>
  );
}
