import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { CreditCard, Wallet as WalletIcon, Clock, Plus } from 'lucide-react';

interface Transaction {
  transaction_id: string;
  amount: number;
  transaction_type: string;
  created_at: string;
}

interface PaymentMethod {
  payment_method_id: string;
  card_last4: string;
  is_default: boolean;
}

const Wallet: React.FC = () => {
  const [balance, setBalance] = useState<number>(0);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);
  const [topupAmount, setTopupAmount] = useState<string>('500');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = async () => {
    try {
      setLoading(true);
      const [balanceRes, transRes, pmRes] = await Promise.all([
        api.get('/wallet/balance'),
        api.get('/wallet/transactions'),
        api.get('/wallet/payment-methods')
      ]);
      setBalance(balanceRes.data.balance);
      setTransactions(transRes.data);
      setPaymentMethods(pmRes.data);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to load wallet data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleTopup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await api.post('/wallet/topup', { amount: parseFloat(topupAmount) });
      fetchData(); // Refresh data
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to top up wallet');
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-skeuo-text-muted">Loading wallet...</div>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-skeuo-text">Wallet & Billing</h1>
      </div>

      {error && (
        <div className="bg-red-100/50 text-red-600 p-4 rounded-xl text-sm border border-red-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Balance Card */}
        <div className="skeuo-panel p-6 flex flex-col justify-between relative overflow-hidden bg-gradient-to-br from-skeuo-bg to-skeuo-surface">
          <div className="absolute top-0 right-0 p-4 opacity-10">
            <WalletIcon size={120} />
          </div>
          <div>
            <p className="text-sm font-semibold text-skeuo-text-muted mb-1">Available Balance</p>
            <h2 className="text-5xl font-bold text-skeuo-accent">₹{balance.toFixed(2)}</h2>
          </div>
          
          <form onSubmit={handleTopup} className="mt-8 flex gap-3 z-10">
            <div className="skeuo-text-field-group flex-1">
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-skeuo-text-muted font-bold">₹</span>
                <input
                  type="number"
                  min="100"
                  step="1"
                  value={topupAmount}
                  onChange={(e) => setTopupAmount(e.target.value)}
                  className="skeuo-input pl-8 w-full"
                />
              </div>
            </div>
            <button type="submit" className="skeuo-btn skeuo-btn-primary whitespace-nowrap">
              <Plus size={18} />
              <span>Top Up</span>
            </button>
          </form>
        </div>

        {/* Payment Methods */}
        <div className="skeuo-panel p-6">
          <div className="flex items-center gap-2 mb-6">
            <CreditCard className="text-skeuo-accent" />
            <h3 className="text-lg font-bold">Payment Methods</h3>
          </div>
          
          {paymentMethods.length === 0 ? (
            <p className="text-skeuo-text-muted text-sm">No payment methods linked.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {paymentMethods.map(pm => (
                <div key={pm.payment_method_id} className="p-4 rounded-xl border-2 border-skeuo-accent/20 bg-white/40 dark:bg-black/20 flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-6 bg-slate-800 rounded flex items-center justify-center text-white text-[10px] font-bold">
                      CARD
                    </div>
                    <div>
                      <p className="font-mono font-bold tracking-widest text-sm">•••• {pm.card_last4}</p>
                      {pm.is_default && <span className="text-[10px] text-skeuo-accent font-bold">DEFAULT</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Transactions List */}
      <div className="skeuo-panel p-6">
        <div className="flex items-center gap-2 mb-6">
          <Clock className="text-skeuo-text-muted" />
          <h3 className="text-lg font-bold">Recent Transactions</h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-skeuo-accent/10">
                <th className="p-3 text-xs font-bold text-skeuo-text-muted uppercase tracking-wider">Date</th>
                <th className="p-3 text-xs font-bold text-skeuo-text-muted uppercase tracking-wider">Type</th>
                <th className="p-3 text-xs font-bold text-skeuo-text-muted uppercase tracking-wider text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {transactions.length === 0 ? (
                <tr>
                  <td colSpan={3} className="p-4 text-center text-skeuo-text-muted">No transactions yet</td>
                </tr>
              ) : (
                transactions.map(t => (
                  <tr key={t.transaction_id} className="border-b border-skeuo-accent/5 last:border-0 hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                    <td className="p-3 text-sm">{new Date(t.created_at).toLocaleString()}</td>
                    <td className="p-3 text-sm font-semibold">{t.transaction_type}</td>
                    <td className={`p-3 text-sm font-bold text-right ${t.amount >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {t.amount >= 0 ? '+' : ''}₹{Math.abs(t.amount).toFixed(2)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Wallet;
