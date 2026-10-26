import { ThemeToggle } from '../theme/ThemeProvider';
import { Select } from '../components/Select';
import { api } from '../api';
import { returnPath } from '../community/common';
import { useEffect, useState, type FormEvent } from 'react';
import { ActionButton, Brand, Eyebrow, Panel } from '../components/ui';
import { MIN_PASSWORD_LENGTH, passwordLength, validateField, validateRegistration, type RegistrationField, type RegistrationValues } from './validation';

const emptyValues: RegistrationValues = { username: '', email: '', phone: '', country_code: '+91', password: '', confirmPassword: '' };
const inputClass = 'w-full rounded-xl border bg-input px-4 py-3.5 text-sm text-cream placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-amber/30';

export function RegisterPage() {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState('');
  const [values, setValues] = useState<RegistrationValues>(emptyValues);
  const [changed, setChanged] = useState<Partial<Record<RegistrationField, boolean>>>({});
  const [attempted, setAttempted] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [completeName, setCompleteName] = useState<string | null>(null);
  useEffect(() => { document.title = 'Register — OUT. Cricket Draft'; }, []);

  const error = (field: RegistrationField) => (field === 'email' ? changed.email : changed[field] || attempted) ? validateField(field, values) : undefined;
  const setField = (field: RegistrationField, value: string) => {
    setFailure('');
    setValues((current) => ({ ...current, [field]: value }));
    setChanged((current) => ({ ...current, [field]: field === 'email' ? false : true }));
  };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAttempted(true); setChanged(current => ({ ...current, email: true }));
    const errors = validateRegistration(values);
    const first = (Object.keys(emptyValues) as RegistrationField[]).find((field) => errors[field]);
    if (first) { document.getElementById(first)?.focus(); return; }
    if (busy) return;
    setBusy(true); setFailure('');
    try {
      const { confirmPassword: _confirm, ...body } = values;
      await api('/auth/me').catch(() => {});
      await api('/auth/register', body);
      setCompleteName(values.username); setValues(emptyValues);
    } catch (error) { setFailure((error as Error).message); }
    finally { setBusy(false); }
  };
  const length = passwordLength(values.password);
  const meter = length === 0 ? 0 : length < MIN_PASSWORD_LENGTH ? 1 : length < 12 ? 2 : length < 20 ? 3 : 4;

  return <main className="mx-auto flex min-h-dvh w-full max-w-7xl flex-col px-5 pb-10 pt-6 sm:px-8 lg:px-12 lg:pt-9">
    <header className="flex flex-wrap gap-3 items-center justify-between border-b border-neutral/10 pb-5"><a href="/" aria-label="OUT. home"><Brand /></a><div className="flex flex-wrap items-center gap-4"><ThemeToggle/><a href="/" className="font-mono text-[10px] tracking-widest text-muted transition hover:text-cream">BACK TO GAME ↗</a></div></header>
    <div className="grid flex-1 items-center gap-10 py-10 lg:grid-cols-[minmax(0,.85fr)_minmax(400px,1fr)] lg:gap-20 lg:py-16">
      <section className="max-w-lg"><Eyebrow className="text-amber">JOIN THE DRAFT</Eyebrow><h1 className="mt-4 text-[clamp(2.8rem,6vw,5.8rem)] font-black leading-[.95] tracking-[-.06em]">Your next<br />innings starts<br /><span className="text-amber">here.</span></h1><p className="mt-6 max-w-md text-base leading-7 text-cream/65">Create your player profile to get ready for the next match. Use a long password or passphrase you haven&apos;t used elsewhere.</p><div className="mt-9 hidden max-w-sm border-t border-neutral/10 pt-6 font-mono text-[11px] leading-6 text-muted lg:block"><span className="text-amber">01</span> Choose your handle<br /><span className="text-amber">02</span> Add your contact details<br /><span className="text-amber">03</span> Protect your account</div></section>

      <Panel className="p-5 sm:p-8 lg:p-9">
        {completeName ? <div className="flex min-h-96 flex-col items-start justify-center"><span className="flex size-12 items-center justify-center rounded-full border border-amber/40 bg-amber/10 text-2xl text-amber" aria-hidden="true">✓</span><Eyebrow className="mt-7 text-amber">Account created</Eyebrow><h2 className="mt-3 text-3xl font-black tracking-tight">Ready, {completeName}.</h2><p className="mt-4 max-w-md text-sm leading-6 text-muted">Your account is ready. Your guest progress is saved, and your trophies will be here when you return.</p><ActionButton onClick={() => { window.location.href = returnPath(); }} className="mt-8">Back to game</ActionButton></div> : <>
          <div className="mb-7"><Eyebrow>Player profile</Eyebrow><h2 className="mt-2 text-2xl font-black tracking-tight">Create your account</h2><p className="mt-2 text-sm text-muted">Phone is optional. Your guest matches and trophies are saved with your account.</p></div>
          {failure && <p role="alert" className="mb-4 text-danger">{failure}</p>}<form noValidate onSubmit={submit} className="space-y-5">
            <div><label htmlFor="username" className="mb-2 block text-xs font-semibold text-cream/80">Username</label><input id="username" name="username" autoComplete="username" value={values.username} onChange={(event) => setField('username', event.target.value)} onBlur={() => setChanged((current) => ({ ...current, username: true }))} placeholder="Your player name" aria-invalid={Boolean(error('username'))} aria-describedby={error('username') ? 'username-error' : undefined} className={`${inputClass} ${error('username') ? 'border-danger' : 'border-neutral/15 focus:border-amber'}`} />{error('username') && <p id="username-error" className="mt-2 text-xs text-danger" role="status">{error('username')}</p>}{changed.username && !error('username') && <p className="mt-2 text-xs text-success" role="status">Username format looks good.</p>}</div>
            <div><label htmlFor="email" className="mb-2 block text-xs font-semibold text-cream/80">Email address</label><input id="email" name="email" type="email" autoComplete="email" value={values.email} onChange={(event) => setField('email', event.target.value)} onBlur={() => setChanged((current) => ({ ...current, email: true }))} placeholder="you@example.com" aria-invalid={Boolean(error('email'))} aria-describedby={error('email') ? 'email-error' : undefined} className={`${inputClass} ${error('email') ? 'border-danger' : 'border-neutral/15 focus:border-amber'}`} />{error('email') && <p id="email-error" className="mt-2 text-xs text-danger" role="status">{error('email')}</p>}{changed.email && !error('email') && <p className="mt-2 text-xs text-success" role="status">Email format looks good.</p>}</div>
            <div><label htmlFor="phone" className="mb-2 block text-xs font-semibold text-cream/80">Phone number (optional)</label><div className="flex gap-2"><Select label="Country code" hideLabel value={values.country_code} onChange={value=>setField('country_code',value)} className="w-36 shrink-0" options={[['🇮🇳 India','+91'],['🇺🇸 USA / 🇨🇦 Canada','+1'],['🇬🇧 UK','+44'],['🇦🇺 Australia','+61'],['🇳🇿 New Zealand','+64'],['🇵🇰 Pakistan','+92'],['🇱🇰 Sri Lanka','+94'],['🇧🇩 Bangladesh','+880'],['🇿🇦 South Africa','+27'],['🇦🇪 UAE','+971']].map(([name,code])=>({value:code,label:`${name} ${code}`,selectedLabel:`${name.split(' ')[0]} ${code}`}))}/><input maxLength={10} id="phone" name="phone" type="tel" inputMode="tel" autoComplete="tel" value={values.phone} onChange={(event) => setField('phone', event.target.value.replace(/\D/g, '').slice(0,10))} onBlur={() => setChanged((current) => ({ ...current, phone: true }))} placeholder="9876543210" aria-invalid={Boolean(error('phone'))} aria-describedby={error('phone') ? 'phone-error' : undefined} className={`${inputClass} ${error('phone') ? 'border-danger' : 'border-neutral/15 focus:border-amber'}`} /></div>{error('phone') && <p id="phone-error" className="mt-2 text-xs text-danger" role="status">{error('phone')}</p>}{changed.phone && !error('phone') && <p className="mt-2 text-xs text-success" role="status">Phone format looks good.</p>}</div>
            <div><label htmlFor="password" className="mb-2 block text-xs font-semibold text-cream/80">Password</label><div className="relative"><input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={values.password} onChange={(event) => setField('password', event.target.value)} onBlur={() => setChanged((current) => ({ ...current, password: true }))} placeholder="Use a long passphrase" aria-invalid={Boolean(error('password'))} aria-describedby="password-feedback" className={`${inputClass} pr-18 ${error('password') ? 'border-danger' : 'border-neutral/15 focus:border-amber'}`} /><button type="button" onClick={() => setShowPassword((shown) => !shown)} aria-label={showPassword ? 'Hide password' : 'Show password'} className="absolute right-4 top-1/2 -translate-y-1/2 font-mono text-[10px] font-semibold tracking-wider text-muted hover:text-cream">{showPassword ? 'HIDE' : 'SHOW'}</button></div>
              <div id="password-feedback" className="mt-3" aria-live="polite"><div className="flex gap-1">{Array.from({ length: 4 }, (_, i) => <span key={i} className={`h-1 flex-1 rounded-full ${i < meter ? 'bg-amber' : 'bg-neutral/10'}`} />)}</div><p className={`mt-2 text-xs ${error('password') ? 'text-danger' : 'text-muted'}`}>{error('password') ?? (length === 0 ? `Use at least ${MIN_PASSWORD_LENGTH} characters. Spaces are welcome.` : 'Length requirement met.')} <span className="ml-1 font-mono text-[10px] text-muted">{length}/{MIN_PASSWORD_LENGTH}</span></p></div>
            </div>
            <div><label htmlFor="confirmPassword" className="mb-2 block text-xs font-semibold text-cream/80">Confirm password</label><div className="relative"><input id="confirmPassword" name="confirmPassword" type={showConfirm ? 'text' : 'password'} autoComplete="new-password" value={values.confirmPassword} onChange={(event) => setField('confirmPassword', event.target.value)} onBlur={() => setChanged((current) => ({ ...current, confirmPassword: true }))} placeholder="Enter it again" aria-invalid={Boolean(error('confirmPassword'))} aria-describedby={changed.confirmPassword || attempted ? 'confirm-feedback' : undefined} className={`${inputClass} pr-18 ${error('confirmPassword') ? 'border-danger' : 'border-neutral/15 focus:border-amber'}`} /><button type="button" onClick={() => setShowConfirm((shown) => !shown)} aria-label={showConfirm ? 'Hide confirmed password' : 'Show confirmed password'} className="absolute right-4 top-1/2 -translate-y-1/2 font-mono text-[10px] font-semibold tracking-wider text-muted hover:text-cream">{showConfirm ? 'HIDE' : 'SHOW'}</button></div>{(changed.confirmPassword || attempted) && <p id="confirm-feedback" className={`mt-2 text-xs ${error('confirmPassword') ? 'text-danger' : 'text-success'}`} role="status">{error('confirmPassword') ?? 'Passwords match.'}</p>}</div>
            <div className="pt-2"><ActionButton type="submit" disabled={busy} className="w-full">{busy ? 'Creating account…' : 'Register'} <span className="ml-2" aria-hidden="true">↗</span></ActionButton><p className="mt-3 text-center text-xs leading-5 text-muted">Already registered? <a href={"/login?returnTo=" + encodeURIComponent(returnPath())} className="text-amber">Sign in</a> or <a href="/" className="text-amber">play as a guest</a>.</p></div>
          </form>
        </>}
      </Panel>
    </div>
  </main>;
}
