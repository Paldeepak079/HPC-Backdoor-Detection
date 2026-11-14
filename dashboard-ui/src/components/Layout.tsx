import React, { useState } from 'react';
import { motion } from 'framer-motion';
import s from './Layout.module.css';

export type Page = 'overview' | 'traces' | 'model';

interface NavItemDef {
  id: Page;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItemDef[] = [
  { id: 'overview', label: 'Command Center', icon: '⬡' },
  { id: 'traces', label: 'Trace Explorer', icon: '≡' },
  { id: 'model', label: 'Model Insights', icon: '◎' },
];

interface LayoutProps {
  currentPage: Page;
  onNavigate: (page: Page) => void;
  children: React.ReactNode;
}

export default function Layout({ currentPage, onNavigate, children }: LayoutProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={s.layout}>
      <div className={`bg-blobs`} />
      <a className="skip-link" href="#main-content">Skip to content</a>

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
            <motion.button
              key={item.id}
              className={`${s.navItem} ${currentPage === item.id ? s.active : ''}`}
              onClick={() => onNavigate(item.id)}
              title={collapsed ? item.label : undefined}
              whileHover={{ x: 3 }}
              whileTap={{ scale: 0.97 }}
              transition={{ type: 'spring', stiffness: 420, damping: 28 }}
            >
              <span className={s.navIcon}>{item.icon}</span>
              <span className={s.navLabel}>{item.label}</span>
            </motion.button>
          ))}
        </nav>

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

      <div className="mobile-nav" aria-label="Mobile navigation">
        {NAV_ITEMS.map(item => (
          <button key={item.id} className={currentPage === item.id ? 'active' : ''} onClick={() => onNavigate(item.id)}>
            <span>{item.icon}</span><br />{item.label.split(' ')[0]}
          </button>
        ))}
      </div>

      <main className={s.main} id="main-content">
        <motion.div
          className={s.pageWrapper}
          key={currentPage}
          initial={{ opacity: 0, y: 10, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
        >
          {children}
        </motion.div>
      </main>
    </div>
  );
}
