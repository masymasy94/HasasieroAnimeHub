import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getDownloads } from '../../api/downloads';

const SIDEBAR_KEY = 'sidebar-collapsed';

const NAV_ITEMS = [
  { to: '/search', label: 'Cerca' },
  { to: '/downloads', label: 'Downloads' },
  { to: '/tracked', label: 'Serie Seguite' },
  { to: '/scheduled', label: 'Programmati' },
  { to: '/settings', label: 'Impostazioni' },
];

const NAV_ICONS: Record<string, React.ReactNode> = {
  '/search': (
    <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  ),
  '/downloads': (
    <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
  ),
  '/tracked': (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
    </svg>
  ),
  '/scheduled': (
    <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  ),
  '/settings': (
    <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  ),
};

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem(SIDEBAR_KEY) === 'true';
  });

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, String(collapsed));
  }, [collapsed]);

  const { data } = useQuery({
    queryKey: ['downloads', 'active'],
    queryFn: () => getDownloads(['queued', 'downloading', 'finalizing']),
    refetchInterval: 10000,
  });

  const activeCount = data?.downloads?.length ?? 0;

  return (
    <aside
      className={`${
        collapsed ? 'w-16' : 'w-56'
      } h-screen bg-bg-navbar border-r border-border flex flex-col flex-shrink-0 transition-[width] duration-200 ease-in-out`}
    >
      <div className={`flex items-center ${collapsed ? 'justify-center p-3' : 'justify-between p-5'}`}>
        {!collapsed && (
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-accent truncate">AnimeHub</h1>
            <p className="text-[11px] text-text-secondary tracking-wide">HASASIERO</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="p-1.5 rounded-md text-text-secondary hover:text-text-white hover:bg-bg-hover transition-colors"
          title={collapsed ? 'Espandi menu' : 'Comprimi menu'}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {collapsed ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7M19 19l-7-7 7-7" />
            )}
          </svg>
        </button>
      </div>

      <nav className={`flex-1 ${collapsed ? 'px-2' : 'px-3'} space-y-0.5`}>
        {NAV_ITEMS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `flex items-center ${collapsed ? 'justify-center' : 'gap-3'} px-3 py-2.5 rounded-[5px] text-[13px] font-medium transition-colors relative ${
                isActive
                  ? 'bg-accent/15 text-accent'
                  : 'text-text-secondary hover:text-text-white hover:bg-bg-hover'
              }`
            }
          >
            {NAV_ICONS[to]}
            {!collapsed && <span className="truncate">{label}</span>}
            {to === '/downloads' && activeCount > 0 && (
              <span
                className={`${
                  collapsed
                    ? 'absolute -top-1 -right-1 px-1 py-0.5 text-[9px]'
                    : 'ml-auto px-1.5 py-0.5 text-[10px]'
                } font-bold bg-accent text-white rounded-full min-w-[18px] text-center`}
              >
                {activeCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className={`border-t border-border ${collapsed ? 'p-2 text-center' : 'p-4'}`}>
        <p className="text-[10px] text-text-secondary">{collapsed ? 'v0.1' : 'v0.1.0'}</p>
      </div>
    </aside>
  );
}
