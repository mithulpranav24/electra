import type { ReactNode } from 'react';
import { BatteryCharging, MapPin, ShieldCheck } from 'lucide-react';
import { BrandMark } from './BrandMark';

export function AuthLayout({ children, mode }: { children: ReactNode; mode: 'login' | 'register' }) {
  return (
    <main className="min-h-screen lg:grid lg:grid-cols-[minmax(22rem,0.9fr)_minmax(34rem,1.1fr)]">
      <section className="relative hidden min-h-screen overflow-hidden bg-[var(--night)] p-10 text-white lg:flex lg:flex-col lg:justify-between xl:p-14">
        <div className="absolute inset-y-0 right-0 w-px bg-white/10" />
        <div className="absolute -right-24 top-24 size-80 rounded-full border border-[var(--amber)]/20" />
        <div className="absolute -right-10 top-38 size-52 rounded-full border border-[var(--amber)]/15" />
        <BrandMark inverse />

        <div className="relative max-w-xl">
          <p className="mb-4 text-xs font-extrabold uppercase tracking-[0.2em] text-[var(--amber)]">One network. Every charge.</p>
          <h1 className="font-display text-5xl font-bold leading-[1.04] tracking-[-0.045em] xl:text-6xl">
            Charge with a clear next step.
          </h1>
          <p className="mt-5 max-w-lg text-lg leading-7 text-white/68">
            Find compatible ports, reserve with confidence, and keep your vehicles and balance ready from one dependable workspace.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-4 border-t border-white/10 pt-6 text-sm text-white/65">
          <div><MapPin size={18} className="mb-2 text-[var(--amber)]" /><span>Multi-operator search</span></div>
          <div><BatteryCharging size={18} className="mb-2 text-[var(--amber)]" /><span>Vehicle-aware charging</span></div>
          <div><ShieldCheck size={18} className="mb-2 text-[var(--amber)]" /><span>Protected reservations</span></div>
        </div>
      </section>

      <section className="flex min-h-screen items-center justify-center px-4 py-8 sm:px-8 lg:px-12">
        <div className="w-full max-w-[31rem]">
          <div className="mb-8 lg:hidden"><BrandMark /></div>
          <div className="mb-7">
            <p className="mb-2 text-xs font-extrabold uppercase tracking-[0.16em] text-[var(--teal)]">{mode === 'login' ? 'Welcome back' : 'Create your driver account'}</p>
            <h1 className="font-display text-4xl font-bold tracking-[-0.035em]">{mode === 'login' ? 'Continue your journey' : 'Get road-ready'}</h1>
            <p className="mt-2 text-[var(--steel)]">{mode === 'login' ? 'Sign in to access your Electra workspace.' : 'Set up your account now; add a vehicle and funds after sign-in.'}</p>
          </div>
          <div className="surface p-5 sm:p-7">{children}</div>
        </div>
      </section>
    </main>
  );
}
