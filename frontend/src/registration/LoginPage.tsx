import { ThemeToggle } from '../theme/ThemeProvider';
import { useState, type FormEvent } from 'react';
import { api } from '../api';
import { ActionButton, Brand, Panel } from '../components/ui';
export function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState(''); const [password, setPassword] = useState('');
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault(); if (busy) return; setBusy(true); setError('');
    try { await api('/auth/login', { email, password }); window.location.assign('/'); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  return <main className="mx-auto max-w-lg px-5 py-12"><header className="flex items-center justify-between gap-4"><a href="/"><Brand/></a><ThemeToggle/></header><Panel className="mt-12 p-8"><h1 className="text-3xl font-bold">Sign in</h1><form onSubmit={submit} className="mt-6 space-y-5">
    <label className="block">Email<input required type="email" autoComplete="username" maxLength={254} value={email} onChange={e=>setEmail(e.target.value)} className="mt-2 w-full rounded-xl bg-input p-3" /></label>
    <div><label htmlFor="login-password" className="block">Password</label><div className="relative mt-2"><input id="login-password" required type={showPassword ? 'text' : 'password'} autoComplete="current-password" maxLength={128} value={password} onChange={e=>setPassword(e.target.value)} className="w-full rounded-xl bg-input p-3 pr-20" /><button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} aria-controls="login-password" onClick={()=>setShowPassword(shown=>!shown)} className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-amber">{showPassword ? 'HIDE' : 'SHOW'}</button></div></div>
    {error && <p role="alert" className="text-danger">{error}</p>}<ActionButton disabled={busy} type="submit">{busy ? 'Signing in…' : 'Sign in'}</ActionButton>
  </form><a className="mt-6 block text-amber" href="/register">Create an account</a><a href="/" className="mt-4 block text-muted">Continue as guest</a></Panel></main>;
}
