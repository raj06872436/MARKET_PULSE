import type { ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import { SHARED_PARAMS } from "../hooks/useFilters";
import type { User } from "../types/api";

const NAV = [
  { to: "/", label: "Overview" },
  { to: "/explore", label: "Explore" },
  { to: "/sentiment", label: "Sentiment" },
  { to: "/compare", label: "Compare" },
  { to: "/forecasts", label: "Forecasts" },
  { to: "/insights", label: "Insights" },
  { to: "/watchlists", label: "Watchlists" },
  { to: "/sources", label: "Sources" },
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
  const { search } = useLocation();
  const carried = sharedSearch(search);
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 md:flex-row">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow">
        Skip to content
      </a>
      <aside className="border-b border-slate-200 bg-white md:flex md:w-56 md:shrink-0 md:flex-col md:border-r md:border-b-0">
        <div className="flex items-start justify-between gap-2 px-4 py-4">
          <div>
            <div className="text-lg font-semibold">MarketPulse AI</div>
            {workspaceName && <div className="text-sm text-slate-500">{workspaceName}</div>}
          </div>
          <div className="flex gap-3 text-sm md:hidden">
            <Link to="/account" className="text-slate-600 underline">Account</Link>
            <button onClick={onSignOut} className="text-slate-600 underline">Sign out</button>
          </div>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 pb-3 md:flex-col md:overflow-visible">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={{ pathname: item.to, search: carried }}
              end={item.to === "/"}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-md px-3 py-2 text-sm ${
                  isActive ? "bg-indigo-50 font-medium text-indigo-700" : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto hidden border-t border-slate-100 px-4 py-3 text-sm md:block">
          <Link to="/account" className="block truncate text-slate-600 hover:underline" title={user.email}>{user.email}</Link>
          <button onClick={onSignOut} className="mt-1 text-slate-500 hover:text-slate-800 hover:underline">Sign out</button>
        </div>
      </aside>
      <main id="main" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 focus:outline-none md:px-8">{children}</main>
    </div>
  );
}
