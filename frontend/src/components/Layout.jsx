import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { FileSearch, History as HistoryIcon, LayoutDashboard, Menu, PlusCircle, X } from 'lucide-react';
import { api } from '../services/api.js';

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/analyze', label: 'New Analysis', icon: PlusCircle },
  { to: '/history', label: 'History', icon: HistoryIcon },
];

function Brand() {
  return (
    <div className="brand">
      <div className="brand-mark"><FileSearch size={19} /></div>
      <span>Resume<b>IQ</b></span>
    </div>
  );
}

function ServerStatus() {
  const [health, setHealth] = useState(null);
  const { pathname } = useLocation();

  useEffect(() => {
    let alive = true;
    api.healthStatus().then((h) => alive && setHealth(h));
    return () => { alive = false; };
  }, [pathname]);

  let tone = '';
  let label = 'Checking server…';
  let detail = '';
  if (health) {
    if (health.status === 'ok') { tone = 'ok'; label = 'Backend connected'; detail = 'Database is working'; }
    else if (health.status === 'degraded') { tone = 'bad'; label = 'Database unavailable'; detail = 'Analyses cannot be saved right now'; }
    else { tone = 'bad'; label = 'Backend offline'; detail = 'Start the Flask server'; }
  }
  return (
    <div className="sidebar-foot">
      <div className="status-row"><span className={`dot ${tone}`} />{label}</div>
      {detail && <div className="muted" style={{ marginTop: 2 }}>{detail}</div>}
    </div>
  );
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => { setOpen(false); window.scrollTo(0, 0); }, [pathname]);

  return (
    <div className="app">
      <aside className={`sidebar ${open ? 'open' : ''}`} aria-label="Main navigation">
        <Brand />
        <nav className="nav">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              <Icon size={18} />{label}
            </NavLink>
          ))}
        </nav>
        <ServerStatus />
      </aside>
      <div className={`scrim ${open ? 'open' : ''}`} onClick={() => setOpen(false)} />
      <div className="main">
        <header className="topbar">
          <Brand />
          <button className="btn btn-ghost icon-btn" onClick={() => setOpen((o) => !o)} aria-label={open ? 'Close menu' : 'Open menu'}>
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </header>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  );
}
