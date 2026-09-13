import { useCallback, useEffect, useState } from 'react';
import { Building2, CalendarClock, IndianRupee, Radio, Wrench } from 'lucide-react';
import { authService, reportService } from '../../services/api';
import type { CompanyMembership, OperatorReport } from '../../types';
import { getErrorMessage } from '../../lib/errors';
import { formatCurrency, shortId } from '../../lib/format';
import { EmptyState, ErrorState, LoadingState } from '../../ui/Feedback';
import { PageHeader, SectionHeader } from '../../ui/Page';
import { PeakHoursChart } from '../../components/reports/PeakHoursChart';
import { RankedBarChart } from '../../components/reports/RankedBarChart';
import { RevenueTrendChart } from '../../components/reports/RevenueTrendChart';
import { UtilizationMeter } from '../../components/reports/UtilizationMeter';

export default function OperatorReports() {
  const [memberships, setMemberships] = useState<CompanyMembership[]>([]);
  const [companyId, setCompanyId] = useState('');
  const [report, setReport] = useState<OperatorReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadReport = useCallback(async (targetCompanyId: string, showLoader = true) => {
    if (showLoader) setIsLoading(true);
    setError('');
    try {
      setReport(await reportService.getOperatorReport(targetCompanyId));
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'The station report could not be loaded for this company.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadWorkspace = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const assignedMemberships = await authService.getMyCompanies();
      setMemberships(assignedMemberships);
      const firstCompanyId = assignedMemberships[0]?.company_id ?? '';
      setCompanyId(firstCompanyId);
      if (firstCompanyId) await loadReport(firstCompanyId, false);
      else setReport(null);
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Your operator assignments could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }, [loadReport]);

  useEffect(() => { void loadWorkspace(); }, [loadWorkspace]);

  if (isLoading) return <div className="surface"><LoadingState label="Loading station report" /></div>;
  if (!companyId) return <div className="surface"><EmptyState title="No company assignment" description="An administrator must assign your operator account to a company before reports are available." icon={<Building2 size={24} />} /></div>;
  if (error || !report) return <ErrorState description={error || 'The station report could not be loaded.'} onRetry={() => void loadReport(companyId)} />;

  const stats = [
    { label: "Today's reservations", value: report.todays_reservations, icon: CalendarClock, tone: 'bg-[var(--blue-soft)] text-[#285270]' },
    { label: 'Active sessions', value: report.active_sessions, icon: Radio, tone: 'bg-[var(--teal-soft)] text-[var(--teal-dark)]' },
    { label: 'Revenue (30d, paid)', value: formatCurrency(report.revenue), icon: IndianRupee, tone: 'bg-[var(--amber-soft)] text-[#6f500c]' },
    { label: 'Maintenance alerts', value: report.maintenance_alerts, icon: Wrench, tone: report.maintenance_alerts ? 'bg-[var(--red-soft)] text-[var(--red)]' : 'bg-[var(--paper-muted)] text-[var(--steel)]' },
  ];

  return (
    <div className="flex flex-col gap-7 enter-up">
      <PageHeader eyebrow="Operator workspace" title="Station reporting" description="Revenue, utilization, and demand trends for your company's stations." />

      {memberships.length > 1 && (
        <div className="surface flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div><p className="text-sm font-bold">Company assignment</p><p className="text-xs text-[var(--steel)]">Switch between companies assigned to your operator account.</p></div>
          <select className="field-control sm:max-w-sm" value={companyId} onChange={(event) => { const id = event.target.value; setCompanyId(id); void loadReport(id); }} aria-label="Select company assignment">
            {memberships.map((membership) => <option key={membership.membership_id} value={membership.company_id}>Company {shortId(membership.company_id, 12)}</option>)}
          </select>
        </div>
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Station overview">
        {stats.map(({ label, value, icon: Icon, tone }) => (
          <div key={label} className="surface flex items-center gap-4 p-4">
            <span className={`flex size-11 items-center justify-center rounded-full ${tone}`}><Icon size={20} /></span>
            <div><p className="font-data text-2xl font-bold">{value}</p><p className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">{label}</p></div>
          </div>
        ))}
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(16rem,0.6fr)]">
        <div className="surface p-5 sm:p-6">
          <SectionHeader title="Revenue (last 30 days)" description="Paid invoices for this company's stations, by day." />
          <div className="mt-4"><RevenueTrendChart data={report.revenue_by_day} /></div>
        </div>
        <div className="surface p-5 sm:p-6">
          <SectionHeader title="Charger utilization" description="Share of active ports currently occupied." />
          <div className="mt-6"><UtilizationMeter percent={report.charger_utilization_pct} /></div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <div className="surface p-5 sm:p-6">
          <SectionHeader title="Peak hours" description="Reservations by hour of day, last 30 days." />
          <div className="mt-4"><PeakHoursChart data={report.peak_hours} /></div>
        </div>
        <div className="surface p-5 sm:p-6">
          <SectionHeader title="Queue statistics" description="Drivers currently waitlisted, by station." />
          <div className="mt-4">
            <RankedBarChart emptyLabel="No drivers are currently waitlisted." data={report.queue_statistics.map((row) => ({ label: row.name, value: row.queue_length }))} />
          </div>
        </div>
      </section>
    </div>
  );
}
