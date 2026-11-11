import type { ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import { SHARED_PARAMS } from "../hooks/useFilters";
import type { User } from "../types/api";
import { Icon, type IconName, Logo } from "./Icon";

const NAV: { to: string; label: string; icon: IconName; group: "analyse" | "manage" }[] = [
  { to: "/", label: "Overview", icon: "overview", group: "analyse" },
  { to: "/explore", label: "Explore", icon: "explore", group: "analyse" },
  { to: "/sentiment", label: "Sentiment", icon: "sentiment", group: "analyse" },
  { to: "/compare", label: "Compare", icon: "compare", group: "analyse" },
  { to: "/forecasts", label: "Forecasts", icon: "forecasts", group: "analyse" },
  { to: "/insights", label: "Insights", icon: "insights", group: "analyse" },
  { to: "/watchlists", label: "Watchlists", icon: "watchlists", group: "manage" },
  { to: "/sources", label: "Sources", icon: "sources", group: "manage" },
];

/** Carry the shared filters (watchlist, dates, sources) from page to page. */
function sharedSearch(search: string): string {
  const current = new URLSearchParams(search);
  const next = new URLSearchParams();
  for (const key of SHARED_PARAMS) current.getAll(key).forEach((v) => next.append(key, v));
  const text = next.toString();
  return text ? `?${text}` : "";
}

export function Layout({ workspaceName, user, onSignOut, children }: {
  workspaceName?: string; user: User; onSignOut: () => void; children: ReactNode;
}) {
  const { search, pathname } = useLocation();
  const carried = sharedSearch(search);
  const initial = user.email.slice(0, 1).toUpperCase();

  const navItem = (item: (typeof NAV)[number]) => (
    <NavLink
      key={item.to}
      to={{ pathname: item.to, search: carried }}
      end={item.to === "/"}
      className={({ isActive }) =>
        `group flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition-colors ${
          isActive
            ? "bg-indigo-50 font-medium text-indigo-700 md:bg-white md:shadow-card md:ring-1 md:ring-slate-200/80"
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        }`
      }
    >
      {({ isActive }) => (
        <>
          <Icon name={item.icon} className={`h-4 w-4 ${isActive ? "text-indigo-600" : "text-slate-400 group-hover:text-slate-600"}`} />
          {item.label}
        </>
      )}
    </NavLink>
  );

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 md:flex-row">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow">
        Skip to content
      </a>
      <aside className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur md:h-screen md:w-60 md:shrink-0 md:border-r md:border-b-0 md:bg-slate-50/60">
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between gap-2 px-4 py-3 md:px-5 md:py-5">
            <Link to={{ pathname: "/", search: carried }} className="flex min-w-0 items-center gap-2.5">
              <Logo className="h-8 w-8 shrink-0" />
              <div className="min-w-0">
                <div className="text-[15px] font-semibold leading-tight tracking-tight">MarketPulse <span className="text-indigo-600">AI</span></div>
                {workspaceName && <div className="truncate text-xs text-slate-500">{workspaceName}</div>}
              </div>
            </Link>
            <div className="flex items-center gap-1 md:hidden">
              <Link to="/account" aria-label="Account" title={user.email}
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
                  pathname === "/account" ? "bg-indigo-600 text-white" : "bg-indigo-100 text-indigo-700"
                }`}>
                {initial}
              </Link>
              <button onClick={onSignOut} aria-label="Sign out" title="Sign out"
                className="flex h-8 w-8 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-800">
                <Icon name="logout" />
              </button>
            </div>
          </div>
          <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 pb-2.5 [scrollbar-width:none] md:flex-1 md:flex-col md:overflow-visible md:pb-0">
            <div className="hidden px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400 md:block">Analyse</div>
            {NAV.filter((n) => n.group === "analyse").map(navItem)}
            <div className="hidden px-3 pb-1.5 pt-5 text-[11px] font-semibold uppercase tracking-wider text-slate-400 md:block">Manage</div>
            {NAV.filter((n) => n.group === "manage").map(navItem)}
          </nav>
          <div className="hidden border-t border-slate-200 p-3 md:block">
            <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
              <Link to="/account" title={user.email}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">
                {initial}
              </Link>
              <div className="min-w-0 flex-1">
                <Link to="/account" className="block truncate text-sm font-medium text-slate-700 hover:text-slate-900" title={user.email}>
                  {user.email}
                </Link>
                <div className="text-xs capitalize text-slate-500">{user.role}</div>
              </div>
              <button onClick={onSignOut} aria-label="Sign out" title="Sign out"
                className="rounded-md p-1.5 text-slate-400 hover:bg-slate-200/60 hover:text-slate-700">
                <Icon name="logout" />
              </button>
            </div>
          </div>
        </div>
      </aside>
      <main id="main" tabIndex={-1} className="min-w-0 flex-1 focus:outline-none">
        <div key={pathname} className="mx-auto w-full max-w-7xl animate-fade-in px-4 py-6 sm:px-6 md:px-8 md:py-8">{children}</div>
      </main>
    </div>
  );
}
