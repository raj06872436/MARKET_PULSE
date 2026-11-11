import type { ReactNode } from "react";

import { Icon, type IconName } from "./Icon";

export function EmptyState({ title, children, icon = "inbox" }: { title: string; children?: ReactNode; icon?: IconName }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white/60 px-6 py-12 text-center">
      <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
        <Icon name={icon} className="h-5 w-5" />
      </div>
      <div className="font-semibold text-slate-800">{title}</div>
      {children && <div className="mx-auto mt-1.5 max-w-md text-sm leading-relaxed text-slate-500">{children}</div>}
    </div>
  );
}
