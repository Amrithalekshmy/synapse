import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../App';
import {
  LayoutDashboard, MessageSquare, Upload, ClipboardCheck,
  CalendarRange, BarChart3, AlertTriangle, BookOpen,
  AlertCircle, FileText, Settings, LogOut
} from 'lucide-react';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { section: 'Field Operations' },
  { to: '/supervisor', icon: MessageSquare, label: 'Supervisor Input' },
  { to: '/ingest', icon: Upload, label: 'Upload & Ingest' },
  { section: 'Planning' },
  { to: '/review', icon: ClipboardCheck, label: 'Review Queue' },
  { to: '/schedule', icon: CalendarRange, label: 'Schedule' },
  { to: '/conflicts', icon: AlertCircle, label: 'Conflicts' },
  { section: 'Intelligence' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/risk', icon: AlertTriangle, label: 'Risk Dashboard' },
  { to: '/knowledge', icon: BookOpen, label: 'Knowledge Base' },
  { section: 'System' },
  { to: '/audit', icon: FileText, label: 'Audit Trail' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  const currentPage = NAV_ITEMS.find(
    (item) => item.to && (item.to === location.pathname || (item.to !== '/' && location.pathname.startsWith(item.to)))
  );
  const pageTitle = currentPage?.label || 'SYNAPSE';

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-mark">S</div>
          <div>
            <div className="sidebar-brand-name">SYNAPSE</div>
            <div className="sidebar-brand-sub">Oil India &middot; SIH26122</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item, i) => {
            if (item.section) {
              return <div key={i} className="sidebar-section">{item.section}</div>;
            }
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
              >
                <Icon />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">
              {(user?.display_name || user?.username || '?')[0].toUpperCase()}
            </div>
            <div>
              <div className="sidebar-user-name">{user?.display_name || user?.username}</div>
              <div className="sidebar-user-role">{user?.role}</div>
            </div>
          </div>
          <button className="sidebar-logout" onClick={logout}>
            <LogOut size={14} style={{ verticalAlign: -2, marginRight: 6 }} />
            Sign out
          </button>
        </div>
      </aside>

      <div className="main-content">
        <header className="topbar">
          <div className="topbar-title">{pageTitle}</div>
        </header>
        <div className="page-content">
          {children}
        </div>
      </div>
    </div>
  );
}
