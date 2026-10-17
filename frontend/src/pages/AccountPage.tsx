import { useState } from "react";

import { api } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import type { User } from "../types/api";

export function AccountPage({ user, onSignedOut }: { user: User; onSignedOut: () => void }) {
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setError(null);
    try {
      await api.deleteAccount();
      onSignedOut();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete the account");
    }
  }

  return (
    <>
      <PageHeader title="Account" />
      <section className="mb-6 rounded-lg border border-slate-200 bg-white p-4 text-sm">
        <dl className="grid grid-cols-[8rem_1fr] gap-y-2">
          <dt className="text-slate-500">Email</dt><dd>{user.email}</dd>
          <dt className="text-slate-500">Role</dt>
          <dd>{user.role === "admin" ? "Admin: can connect shared sources and rebuild analysis" : "Member"}</dd>
        </dl>
      </section>
      <section className="rounded-lg border border-red-200 bg-white p-4 text-sm">
        <h2 className="font-semibold text-red-800">Delete account</h2>
        <p className="mt-1 text-slate-600">
          Deletes your account, your workspaces, their watchlists, alerts and insights, and every file you uploaded.
          Posts from shared sources stay, since other workspaces use them. This can't be undone.
        </p>
        <label htmlFor="confirm-delete" className="mt-3 block text-slate-700">Type your email to confirm</label>
        <div className="mt-1 flex flex-wrap gap-2">
          <input id="confirm-delete" value={confirm} onChange={(e) => setConfirm(e.target.value)}
            className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-1.5" autoComplete="off" />
          <button disabled={confirm.trim().toLowerCase() !== user.email} onClick={remove}
            className="rounded-md bg-red-700 px-3 py-1.5 font-medium text-white hover:bg-red-800 disabled:opacity-40">
            Delete my account
          </button>
        </div>
        {error && <p role="alert" className="mt-2 rounded-md bg-red-50 px-3 py-2 text-red-700">{error}</p>}
      </section>
    </>
  );
}
