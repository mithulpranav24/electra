import { useCallback, useEffect, useState } from 'react';
import { Activity, Building2, CalendarClock, MapPin, Radio, Users } from 'lucide-react';
import { reportService } from '../../services/api';
import type { AdminReport } from '../../types';
import { getErrorMessage } from '../../lib/errors';
import { ErrorState, LoadingState } from '../../ui/Feedback';
import { PageHeader, SectionHeader } from '../../ui/Page';
import { RankedBarChart } from '../../components/reports/RankedBarChart';
import { RevenueTrendChart } from '../../components/reports/RevenueTrendChart';

export default function AdminReports() {
  const [report, setReport] = useState<AdminReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      setReport(await reportService.getAdminReport());
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'The platform report could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (isLoading) return <div className="surface"><LoadingState label="Loading platform report" /></div>;
  if (error || !report) return <ErrorState description={error || 'The platform report could not be loaded.'} onRetry={() => void load()} />;

  const stats = [
    { label: 'Total users', value: report.total_users, icon: Users, tone: 'bg-[var(--blue-soft)] text-[#285270]' },
    { label: 'Companies', value: report.total_companies, icon: Building2, tone: 'bg-[var(--teal-soft)] text-[var(--teal-dark)]' },
    { label: 'Stations', value: report.total_stations, icon: MapPin, tone: 'bg-[var(--amber-soft)] text-[#6f500c]' },
    { label: 'Active sessions', value: report.active_sessions, icon: Radio, tone: 'bg-[var(--teal-soft)] text-[var(--teal-dark)]' },
    { label: 'Reservations today', value: report.reservations_today, icon: CalendarClock, tone: 'bg-[var(--blue-soft)] text-[#285270]' },
    { label: 'Activity (24h)', value: report.system_activity_24h, icon: Activity, tone: 'bg-[var(--paper-muted)] text-[var(--steel-dark)]' },
  ];

  return (
    <div className="flex flex-col gap-7 enter-up">
      <PageHeader eyebrow="Admin workspace" title="Platform reporting" description="Revenue, system activity, and usage trends across every company on Electra." />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-label="Platform overview">
        {stats.map(({ label, value, icon: Icon, tone }) => (
          <div key={label} className="surface flex items-center gap-4 p-4">
            <span className={`flex size-11 items-center justify-center rounded-full ${tone}`}><Icon size={20} /></span>
            <div><p className="font-data text-2xl font-bold">{value}</p><p className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">{label}</p></div>
          </div>
        ))}
      </section>

      <section className="surface p-5 sm:p-6">
        <SectionHeader title="Revenue (last 30 days)" description="Paid invoices across every company, by day." />
        <div className="mt-4"><RevenueTrendChart data={report.revenue_by_day} /></div>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <div className="surface p-5 sm:p-6">
          <SectionHeader title="Most popular stations" description="Ranked by total charging sessions." />
          <div className="mt-4">
            <RankedBarChart
              emptyLabel="No completed sessions yet."
              data={report.most_popular_stations.map((station) => ({ label: station.name, value: station.session_count }))}
            />
          </div>
        </div>
        <div className="surface p-5 sm:p-6">
          <SectionHeader title="System activity (last 24h)" description="Most frequent audited actions platform-wide." />
          <div className="mt-4">
            <RankedBarChart emptyLabel="No audited activity in the last 24 hours." data={report.top_actions.map((action) => ({ label: action.action, value: action.count }))} />
          </div>
        </div>
      </section>
    </div>
  );
}
