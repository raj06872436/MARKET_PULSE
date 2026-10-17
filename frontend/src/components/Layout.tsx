import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const NAV = [
  { to: "/", label: "Overview" },
  { to: "/watchlists", label: "Watchlists" },
  { to: "/compare", label: "Compare" },
  { to: "/forecasts", label: "Forecasts" },
  { to: "/insights", label: "Insights" },
  { to: "/sources", label: "Sources" },
];

export function Layout({ workspaceName, children }: { workspaceName?: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 md:flex-row">
      <aside className="border-b border-slate-200 bg-white md:w-56 md:shrink-0 md:border-r md:border-b-0">
        <div className="px-4 py-4">
          <div className="text-lg font-semibold">MarketPulse AI</div>
          {workspaceName && <div className="text-sm text-slate-500">{workspaceName}</div>}
        </div>
        <nav className="flex gap-1 overflow-x-auto px-2 pb-3 md:flex-col md:overflow-visible">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
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
      </aside>
      <main className="flex-1 px-4 py-6 md:px-8">{children}</main>
    </div>
  );
}
