import { useEffect, useId, useRef, useState } from 'react';
import { api } from '../api';
import { Panel } from '../components/ui';

type User = {
  id: string;
  username: string;
  email: string;
  mobile: string | null;
  is_admin: boolean;
  is_blocked: boolean;
  created_at: string;
};

type Page = { users: User[]; page: number; page_size: number; total: number };

function GrantAdminDialog({ user, busy, onCancel, onConfirm }: {
  user: User | null;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const title = useId();
  const detail = useId();

  useEffect(() => {
    if (!user) return;
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.showModal();
    return () => {
      dialog.current?.close();
      previous?.focus();
    };
  }, [user]);

  return <dialog ref={dialog} aria-labelledby={title} aria-describedby={detail}
    onCancel={(event) => { event.preventDefault(); if (!busy) onCancel(); }}
    className="m-auto w-[calc(100%_-_2rem)] max-w-sm rounded-2xl border border-neutral/15 bg-panel p-5 text-cream shadow-2xl backdrop:bg-black/60">
    <h2 id={title} className="text-lg font-semibold">Grant administrator access?</h2>
    <p id={detail} className="mt-2 text-[13px] leading-5 text-muted">
      {user?.username} will be able to view analytics, manage users, and grant administrator access to others.
    </p>
    <div className="mt-5 grid grid-cols-2 gap-2 text-xs font-semibold">
      <button type="button" autoFocus disabled={busy} onClick={onCancel}
        className="min-h-11 rounded-lg border border-neutral/15 px-3 transition hover:bg-neutral/5 disabled:opacity-40">Cancel</button>
      <button type="button" disabled={busy} onClick={onConfirm}
        className="min-h-11 rounded-lg bg-accent-fill px-3 text-on-accent transition hover:bg-accent-hover disabled:opacity-40">
        {busy ? 'Granting…' : 'Make admin'}
      </button>
    </div>
  </dialog>;
}

export function UserManagement() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [promote, setPromote] = useState<User | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    setData(null);
    api<Page>(`/admin/users?page=${page}&page_size=10`)
      .then((next) => { if (active) { setData(next); setError(''); } })
      .catch((reason: Error) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [page, refresh]);

  async function changeStatus(user: User) {
    setBusy(`status:${user.id}`);
    setError('');
    try {
      await api(`/admin/users/${user.id}/status`, { blocked: !user.is_blocked });
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function grantAdmin() {
    if (!promote) return;
    setBusy(`admin:${promote.id}`);
    setError('');
    try {
      await api(`/admin/users/${promote.id}/admin`, {});
      setPromote(null);
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError((reason as Error).message);
      setPromote(null);
    } finally {
      setBusy(null);
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return <Panel className="mt-8 p-6">
    <h2 className="text-2xl font-bold">Registered users</h2>
    <p className="mt-2 text-sm text-muted">Manage account access and grant administrator permissions.</p>
    {error && <p role="alert" className="my-4 text-danger">{error}</p>}
    {!data && !error ? <p className="mt-5">Loading users…</p> : data && <>
      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-muted"><tr>{['User', 'Email', 'Mobile', 'Joined', 'Status', 'Actions'].map((heading) => <th key={heading} className="p-3">{heading}</th>)}</tr></thead>
          <tbody>{data.users.map((user) => <tr key={user.id} className="border-t border-neutral/10">
            <td className="p-3 font-bold">{user.username}{user.is_admin && <span className="ml-2 rounded-full border border-neutral/15 px-2 py-0.5 text-[10px] font-semibold text-muted">Admin</span>}</td>
            <td className="p-3">{user.email}</td>
            <td className="whitespace-nowrap p-3">{user.mobile ?? 'Not recorded'}</td>
            <td className="whitespace-nowrap p-3">{new Date(user.created_at).toLocaleDateString()}</td>
            <td className={`p-3 ${user.is_blocked ? 'text-danger' : 'text-success'}`}>{user.is_blocked ? 'Blocked' : 'Active'}</td>
            <td className="p-3"><div className="flex min-w-max gap-2">
              <button type="button" disabled={Boolean(busy) || user.is_admin} onClick={() => void changeStatus(user)}
                className="rounded-lg border border-neutral/20 px-3 py-2 text-xs font-semibold disabled:opacity-40">
                {busy === `status:${user.id}` ? 'Saving…' : user.is_blocked ? 'Unblock' : 'Block'}
              </button>
              {!user.is_admin && <button type="button" disabled={Boolean(busy) || user.is_blocked} title={user.is_blocked ? 'Unblock this account first' : undefined}
                onClick={() => setPromote(user)} className="rounded-lg bg-accent-fill px-3 py-2 text-xs font-semibold text-on-accent disabled:opacity-40">
                Make admin
              </button>}
            </div></td>
          </tr>)}</tbody>
        </table>
      </div>
      <div className="mt-5 flex items-center justify-between gap-4 text-sm">
        <button type="button" disabled={page === 1 || Boolean(busy)} className="font-semibold disabled:text-muted" onClick={() => setPage((value) => value - 1)}>Previous users</button>
        <p>Page {page} of {pages} · {data.total} users</p>
        <button type="button" disabled={page >= pages || Boolean(busy)} className="font-semibold disabled:text-muted" onClick={() => setPage((value) => value + 1)}>Next users</button>
      </div>
    </>}
    <GrantAdminDialog user={promote} busy={busy === `admin:${promote?.id}`} onCancel={() => setPromote(null)} onConfirm={() => void grantAdmin()} />
  </Panel>;
}
