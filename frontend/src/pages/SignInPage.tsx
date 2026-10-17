import { type FormEvent, useState } from "react";

import { api } from "../api/client";
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
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 text-slate-900">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6">
        <h1 className="text-xl font-semibold">MarketPulse AI</h1>
        <p className="mt-1 text-sm text-slate-500">{registering ? "Create an account" : "Sign in to your workspace"}</p>
        <form onSubmit={submit} className="mt-5 space-y-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="email" className="text-sm font-medium text-slate-700">Email</label>
            <input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="password" className="text-sm font-medium text-slate-700">Password</label>
            <input id="password" type="password" required minLength={registering ? 10 : undefined}
              autoComplete={registering ? "new-password" : "current-password"} value={password}
              onChange={(e) => setPassword(e.target.value)} aria-describedby={registering ? "password-hint" : undefined}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
            {registering && <p id="password-hint" className="text-xs text-slate-500">At least 10 characters.</p>}
          </div>
          {error && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          <button disabled={busy} className="w-full rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
            {busy ? "Please wait…" : registering ? "Create account" : "Sign in"}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-600">
          {registering ? "Already have an account?" : "New here?"}{" "}
          <button type="button" onClick={() => { setMode(registering ? "signin" : "register"); setError(null); }}
            className="font-medium text-indigo-700 underline">
            {registering ? "Sign in" : "Create an account"}
          </button>
        </p>
      </div>
    </main>
  );
}
