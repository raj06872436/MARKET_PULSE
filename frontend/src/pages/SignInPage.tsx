import { type FormEvent, useState } from "react";

import { api } from "../api/client";
import { Logo } from "../components/Icon";
import type { User } from "../types/api";

export function SignInPage({ onSignedIn }: { onSignedIn: (user: User) => void }) {
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSignedIn(mode === "signin" ? await api.login(email, password) : await api.register(email, password));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const registering = mode === "register";
  return (
    <main className="grid min-h-screen bg-white text-slate-900 lg:grid-cols-2">
      <section className="relative hidden overflow-hidden bg-gradient-to-br from-indigo-600 via-indigo-700 to-violet-800 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <svg className="pointer-events-none absolute inset-x-0 bottom-24 w-full opacity-25" viewBox="0 0 600 160" preserveAspectRatio="none" aria-hidden>
          <path d="M0 110 L80 100 L130 120 L190 60 L240 90 L300 30 L350 80 L410 70 L470 20 L520 60 L600 40" fill="none" stroke="#fff" strokeWidth="3" strokeLinejoin="round" />
          <path d="M0 140 L90 130 L150 138 L220 110 L280 125 L340 100 L420 118 L500 95 L600 105" fill="none" stroke="#c7d2fe" strokeWidth="2" strokeLinejoin="round" />
        </svg>
        <div className="relative flex items-center gap-2.5">
          <Logo className="h-9 w-9 rounded-lg ring-1 ring-white/30" />
          <span className="text-lg font-semibold tracking-tight">MarketPulse AI</span>
        </div>
        <div className="relative max-w-md">
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">Know what people are saying about your brand, every day.</h2>
          <p className="mt-4 text-indigo-100">
            Track mentions, sentiment and emerging topics for your products and competitors, with every number traceable back to the posts behind it.
          </p>
        </div>
        <ul className="relative grid grid-cols-3 gap-4 text-sm text-indigo-100">
          <li><span className="block text-base font-semibold text-white">Trends</span>week over week</li>
          <li><span className="block text-base font-semibold text-white">Sentiment</span>by topic</li>
          <li><span className="block text-base font-semibold text-white">Forecasts</span>with ranges</li>
        </ul>
      </section>

      <section className="flex items-center justify-center bg-slate-50 px-4 py-12 lg:bg-white">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <Logo className="h-9 w-9" />
            <span className="text-lg font-semibold tracking-tight">MarketPulse AI</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{registering ? "Create your account" : "Welcome back"}</h1>
          <p className="mt-1.5 text-sm text-slate-500">{registering ? "Set up a workspace to start tracking." : "Sign in to your workspace"}</p>
          <form onSubmit={submit} className="mt-8 space-y-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="email" className="text-sm font-medium text-slate-700">Email</label>
              <input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com" className="rounded-lg border px-3 py-2.5 text-sm" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="password" className="text-sm font-medium text-slate-700">Password</label>
              <input id="password" type="password" required minLength={registering ? 10 : undefined}
                autoComplete={registering ? "new-password" : "current-password"} value={password}
                onChange={(e) => setPassword(e.target.value)} aria-describedby={registering ? "password-hint" : undefined}
                className="rounded-lg border px-3 py-2.5 text-sm" />
              {registering && <p id="password-hint" className="text-xs text-slate-500">At least 10 characters.</p>}
            </div>
            {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            <button disabled={busy} className="w-full rounded-lg bg-indigo-600 px-3 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50">
              {busy ? "Please wait…" : registering ? "Create account" : "Sign in"}
            </button>
          </form>
          <p className="mt-6 text-center text-sm text-slate-600">
            {registering ? "Already have an account?" : "New here?"}{" "}
            <button type="button" onClick={() => { setMode(registering ? "signin" : "register"); setError(null); }}
              className="font-medium text-indigo-700 hover:text-indigo-800 hover:underline">
              {registering ? "Sign in" : "Create an account"}
            </button>
          </p>
        </div>
      </section>
    </main>
  );
}
