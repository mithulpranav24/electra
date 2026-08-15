import { useCallback, useEffect, useState } from 'react';
import { CreditCard, Plus, ReceiptText, ShieldCheck, WalletCards } from 'lucide-react';
import { useAuth } from '../../context/auth-context';
import { walletService } from '../../services/api';
import type { PaymentMethod, WalletTransaction } from '../../types';
import { getErrorMessage } from '../../lib/errors';
import { formatCurrency, formatDateTime } from '../../lib/format';
import { Button } from '../../ui/Button';
import { EmptyState, ErrorState, LoadingState } from '../../ui/Feedback';
import { Field } from '../../ui/Field';
import { PageHeader, SectionHeader } from '../../ui/Page';
import { useToast } from '../../ui/ToastContext';
import { Badge } from '../../ui/Badge';

interface WalletData {
  balance: number;
  transactions: WalletTransaction[];
  paymentMethods: PaymentMethod[];
}

const topUpOptions = [500, 1000, 2000];

export default function Wallet() {
  const [data, setData] = useState<WalletData | null>(null);
  const [amount, setAmount] = useState('500');
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const { fetchUser } = useAuth();
  const { pushToast } = useToast();

  const loadWallet = useCallback(async (showLoader = true) => {
    if (showLoader) setIsLoading(true);
    setError('');
    try {
      const [balance, transactions, paymentMethods] = await Promise.all([
        walletService.getBalance(),
        walletService.getTransactions(),
        walletService.getPaymentMethods(),
      ]);
      setData({ balance, transactions, paymentMethods });
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Wallet details could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { void loadWallet(); }, [loadWallet]);

  const handleTopUp = async (event: React.FormEvent) => {
    event.preventDefault();
    const numericAmount = Number(amount);
    if (!Number.isFinite(numericAmount) || numericAmount < 100) {
      setError('Enter a top-up amount of at least ₹100.');
      return;
    }

    setError('');
    setIsSubmitting(true);
    try {
      await walletService.topUp(numericAmount);
      await Promise.all([loadWallet(false), fetchUser()]);
      pushToast({ title: 'Wallet topped up', message: `${formatCurrency(numericAmount)} is now available for charging.`, tone: 'success' });
    } catch (topUpError) {
      setError(getErrorMessage(topUpError, 'The wallet could not be topped up.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-7 enter-up">
      <PageHeader eyebrow="Payments" title="Wallet & billing" description="Keep funds ready for reservation escrow and review every wallet movement." />

      {isLoading ? <div className="surface"><LoadingState label="Loading wallet" /></div> : error && !data ? <ErrorState description={error} onRetry={() => void loadWallet()} /> : data && (
        <>
          <section className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(20rem,0.85fr)]">
            <div className="relative overflow-hidden rounded-[var(--radius-lg)] bg-[var(--night)] p-6 text-white shadow-[var(--shadow-md)] sm:p-8">
              <WalletCards size={180} className="absolute -bottom-12 -right-8 text-white/5" aria-hidden="true" />
              <p className="text-xs font-extrabold uppercase tracking-[0.15em] text-white/50">Available balance</p>
              <p className="font-data mt-2 text-4xl font-bold tracking-[-0.04em] text-[var(--amber)] sm:text-5xl">{formatCurrency(data.balance)}</p>
              <div className="mt-6 flex items-center gap-2 text-sm text-white/62"><ShieldCheck size={17} className="text-[var(--amber)]" /><span>{data.balance >= 1000 ? 'Ready for a ₹1,000 reservation escrow' : `${formatCurrency(1000 - data.balance)} more needed to reserve`}</span></div>
            </div>

            <form onSubmit={handleTopUp} className="surface p-5 sm:p-6">
              <SectionHeader title="Add funds" description="Mock top-ups are credited immediately." />
              <div className="mt-5 flex gap-2" aria-label="Suggested top-up amounts">
                {topUpOptions.map((option) => <button key={option} type="button" className={`min-h-10 flex-1 rounded-lg border px-2 text-sm font-bold transition ${Number(amount) === option ? 'border-[var(--teal)] bg-[var(--teal-soft)] text-[var(--teal-dark)]' : 'border-[var(--line)] bg-white text-[var(--steel-dark)] hover:border-[var(--line-strong)]'}`} onClick={() => setAmount(String(option))}>{formatCurrency(option, 0)}</button>)}
              </div>
              <Field label="Top-up amount" hint="Minimum ₹100." className="mt-4">
                {({ id, describedBy, invalid }) => <div className="relative"><span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 font-bold text-[var(--steel)]">₹</span><input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control field-control-money" type="number" min={100} step={1} value={amount} onChange={(event) => setAmount(event.target.value)} required /></div>}
              </Field>
              {error && <p className="mt-2 text-sm font-semibold text-[var(--red)]" role="alert">{error}</p>}
              <Button type="submit" variant="primary" className="mt-5 w-full" icon={<Plus size={17} />} isLoading={isSubmitting}>Add funds</Button>
            </form>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(18rem,0.65fr)]">
            <div className="surface overflow-hidden">
              <div className="border-b border-[var(--line)] p-5 sm:p-6"><SectionHeader title="Wallet activity" description="Credits, escrow holds, releases, and penalties." /></div>
              {data.transactions.length === 0 ? (
                <EmptyState compact title="No wallet activity yet" description="Top-ups and charging-related wallet movements will appear here." icon={<ReceiptText size={22} />} />
              ) : (
                <>
                  <div className="hidden overflow-x-auto md:block">
                    <table className="w-full border-collapse text-left">
                      <thead className="bg-[#fafbfa] text-xs uppercase tracking-[0.09em] text-[var(--steel)]"><tr><th className="px-5 py-3 font-bold">Date</th><th className="px-5 py-3 font-bold">Activity</th><th className="px-5 py-3 text-right font-bold">Amount</th></tr></thead>
                      <tbody className="divide-y divide-[var(--line)]">
                        {data.transactions.map((transaction) => <tr key={transaction.transaction_id}><td className="whitespace-nowrap px-5 py-4 text-sm text-[var(--steel-dark)]">{formatDateTime(transaction.created_at)}</td><td className="px-5 py-4 text-sm font-bold">{transaction.transaction_type}</td><td className={`font-data whitespace-nowrap px-5 py-4 text-right font-bold ${Number(transaction.amount) >= 0 ? 'text-[var(--teal-dark)]' : 'text-[var(--red)]'}`}>{Number(transaction.amount) >= 0 ? '+' : '−'}{formatCurrency(Math.abs(Number(transaction.amount)))}</td></tr>)}
                      </tbody>
                    </table>
                  </div>
                  <div className="divide-y divide-[var(--line)] md:hidden">
                    {data.transactions.map((transaction) => <div key={transaction.transaction_id} className="flex items-start justify-between gap-4 p-4"><div><p className="text-sm font-bold">{transaction.transaction_type}</p><p className="mt-1 text-xs text-[var(--steel)]">{formatDateTime(transaction.created_at)}</p></div><p className={`font-data shrink-0 font-bold ${Number(transaction.amount) >= 0 ? 'text-[var(--teal-dark)]' : 'text-[var(--red)]'}`}>{Number(transaction.amount) >= 0 ? '+' : '−'}{formatCurrency(Math.abs(Number(transaction.amount)))}</p></div>)}
                  </div>
                </>
              )}
            </div>

            <div className="surface p-5 sm:p-6">
              <SectionHeader title="Payment methods" description="Cards linked to your account." />
              {data.paymentMethods.length === 0 ? (
                <EmptyState compact title="No linked cards" description="Top-up currently uses the project's mock payment flow; card management is not available yet." icon={<CreditCard size={22} />} />
              ) : (
                <div className="mt-5 flex flex-col gap-3">
                  {data.paymentMethods.map((method) => (
                    <div key={method.payment_method_id} className="rounded-[var(--radius-md)] border border-[var(--line)] p-4">
                      <div className="flex items-center justify-between gap-3"><span className="flex size-10 items-center justify-center rounded-lg bg-[var(--night)] text-[var(--amber)]"><CreditCard size={20} /></span>{method.is_default && <Badge tone="success">Default</Badge>}</div>
                      <p className="font-data mt-4 font-bold tracking-[0.12em]">•••• {method.card_last4}</p>
                      <p className="mt-1 text-xs text-[var(--steel)]">Expires {String(method.expiry_month).padStart(2, '0')}/{String(method.expiry_year).slice(-2)}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
