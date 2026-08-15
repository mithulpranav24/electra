import { useCallback, useEffect, useMemo, useState } from 'react';
import { Building2, CircleCheck, Clock3, Pencil, Plus, UserPlus, UsersRound } from 'lucide-react';
import { adminService } from '../../services/api';
import type { Company, CompanyMembership } from '../../types';
import { getErrorMessage } from '../../lib/errors';
import { formatDate, formatDateTime, shortId } from '../../lib/format';
import { Badge } from '../../ui/Badge';
import { Button, IconButton } from '../../ui/Button';
import { Dialog } from '../../ui/Dialog';
import { EmptyState, ErrorState, LoadingState } from '../../ui/Feedback';
import { Field } from '../../ui/Field';
import { PageHeader, SectionHeader } from '../../ui/Page';
import { useToast } from '../../ui/ToastContext';

export default function AdminDashboard() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState('');
  const [memberships, setMemberships] = useState<CompanyMembership[]>([]);
  const [newCompanyName, setNewCompanyName] = useState('');
  const [operatorUserId, setOperatorUserId] = useState('');
  const [error, setError] = useState('');
  const [membershipError, setMembershipError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isAssigning, setIsAssigning] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [editingName, setEditingName] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const { pushToast } = useToast();

  const loadCompanies = useCallback(async () => {
    setError('');
    setIsLoading(true);
    try {
      const result = await adminService.getCompanies();
      setCompanies(result);
      setSelectedCompanyId((current) => result.some((company) => company.company_id === current) ? current : result[0]?.company_id ?? '');
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Companies could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadMemberships = useCallback(async (companyId: string) => {
    if (!companyId) { setMemberships([]); return; }
    setMembershipError('');
    try {
      setMemberships(await adminService.getOperators(companyId));
    } catch (loadError) {
      setMembershipError(getErrorMessage(loadError, 'Operator assignments could not be loaded.'));
    }
  }, []);

  useEffect(() => { void loadCompanies(); }, [loadCompanies]);
  useEffect(() => { void loadMemberships(selectedCompanyId); }, [loadMemberships, selectedCompanyId]);

  const selectedCompany = useMemo(() => companies.find((company) => company.company_id === selectedCompanyId) ?? null, [companies, selectedCompanyId]);
  const activeCompanies = companies.filter((company) => company.is_active).length;
  const deprecatingCompanies = companies.filter((company) => company.is_deprecating).length;

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    const name = newCompanyName.trim();
    if (!name) return;
    setIsCreating(true);
    try {
      const company = await adminService.createCompany({ name });
      setNewCompanyName('');
      await loadCompanies();
      setSelectedCompanyId(company.company_id);
      pushToast({ title: 'Company created', message: `${company.name} is ready for operator assignment.`, tone: 'success' });
    } catch (createError) {
      pushToast({ title: 'Couldn’t create the company', message: getErrorMessage(createError, 'The name may already be in use.'), tone: 'error' });
    } finally {
      setIsCreating(false);
    }
  };

  const handleAssign = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedCompanyId || !operatorUserId.trim()) return;
    setIsAssigning(true);
    try {
      await adminService.assignOperator(selectedCompanyId, operatorUserId.trim());
      setOperatorUserId('');
      await loadMemberships(selectedCompanyId);
      pushToast({ title: 'Operator assigned', message: `The user can now manage ${selectedCompany?.name ?? 'this company'}.`, tone: 'success' });
    } catch (assignError) {
      pushToast({ title: 'Couldn’t assign the operator', message: getErrorMessage(assignError, 'Check that both IDs are valid and the user is eligible.'), tone: 'error' });
    } finally {
      setIsAssigning(false);
    }
  };

  const handleEdit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!editingCompany || !editingName.trim()) return;
    setIsEditing(true);
    try {
      await adminService.updateCompany(editingCompany.company_id, { name: editingName.trim() });
      setEditingCompany(null);
      await loadCompanies();
      pushToast({ title: 'Company updated', tone: 'success' });
    } catch (editError) {
      pushToast({ title: 'Couldn’t update the company', message: getErrorMessage(editError, 'The name may already be in use.'), tone: 'error' });
    } finally {
      setIsEditing(false);
    }
  };

  return (
    <div className="flex flex-col gap-7 enter-up">
      <PageHeader eyebrow="Admin workspace" title="Organization control" description="Create charging companies, assign operators, and monitor organization status." />

      {isLoading ? <div className="surface"><LoadingState label="Loading organizations" /></div> : error ? <ErrorState description={error} onRetry={() => void loadCompanies()} /> : (
        <>
          <section className="grid gap-4 sm:grid-cols-3">
            <div className="surface flex items-center gap-4 p-4"><span className="flex size-11 items-center justify-center rounded-full bg-[var(--blue-soft)] text-[#285270]"><Building2 size={21} /></span><div><p className="font-data text-2xl font-bold">{companies.length}</p><p className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Companies</p></div></div>
            <div className="surface flex items-center gap-4 p-4"><span className="flex size-11 items-center justify-center rounded-full bg-[var(--teal-soft)] text-[var(--teal-dark)]"><CircleCheck size={21} /></span><div><p className="font-data text-2xl font-bold">{activeCompanies}</p><p className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Active</p></div></div>
            <div className="surface flex items-center gap-4 p-4"><span className="flex size-11 items-center justify-center rounded-full bg-[var(--amber-soft)] text-[#70510d]"><Clock3 size={21} /></span><div><p className="font-data text-2xl font-bold">{deprecatingCompanies}</p><p className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Deprecating</p></div></div>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]">
            <div className="surface overflow-hidden">
              <div className="border-b border-[var(--line)] p-5 sm:p-6"><SectionHeader title="Companies" description="Select a company to inspect and manage operator assignments." /></div>
              {companies.length === 0 ? <EmptyState title="No companies yet" description="Create the first operator organization using the form beside this list." icon={<Building2 size={23} />} /> : (
                <div className="divide-y divide-[var(--line)]">
                  {companies.map((company) => {
                    const selected = company.company_id === selectedCompanyId;
                    return (
                      <div key={company.company_id} className={`flex items-center gap-3 p-4 sm:px-5 ${selected ? 'bg-[var(--teal-soft)]/45' : ''}`}>
                        <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setSelectedCompanyId(company.company_id)} aria-pressed={selected}>
                          <div className="flex flex-wrap items-center gap-2"><span className="font-display text-lg font-bold">{company.name}</span><Badge tone={company.is_active ? 'success' : 'danger'}>{company.is_active ? 'Active' : 'Inactive'}</Badge>{company.is_deprecating && <Badge tone="warning">Deprecating</Badge>}</div>
                          <p className="font-data mt-1 text-xs text-[var(--steel)]">{shortId(company.company_id, 16)} · Created {formatDate(company.created_at)}</p>
                        </button>
                        <IconButton label={`Edit ${company.name}`} onClick={() => { setEditingCompany(company); setEditingName(company.name); }}><Pencil size={17} /></IconButton>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <form onSubmit={handleCreate} className="surface h-fit p-5 sm:p-6">
              <SectionHeader title="Create company" description="Names must be unique across the platform." />
              <Field label="Company name" className="mt-5">{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={newCompanyName} onChange={(event) => setNewCompanyName(event.target.value)} placeholder="Electra Mobility Network" required />}</Field>
              <Button type="submit" variant="primary" className="mt-5 w-full" icon={<Plus size={17} />} isLoading={isCreating}>Create company</Button>
            </form>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(20rem,0.8fr)_minmax(0,1.2fr)]">
            <form onSubmit={handleAssign} className="surface h-fit p-5 sm:p-6">
              <SectionHeader title="Assign operator" description={selectedCompany ? `Grant access to ${selectedCompany.name}.` : 'Select a company first.'} />
              <Field label="Company" className="mt-5">{({ id, describedBy, invalid }) => <select id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={selectedCompanyId} onChange={(event) => setSelectedCompanyId(event.target.value)} required><option value="">Select company</option>{companies.filter((company) => company.is_active).map((company) => <option key={company.company_id} value={company.company_id}>{company.name}</option>)}</select>}</Field>
              <Field label="Operator user ID" hint="Paste the user UUID from the user record." className="mt-4">{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control font-data text-sm" value={operatorUserId} onChange={(event) => setOperatorUserId(event.target.value)} placeholder="00000000-0000-0000-0000-000000000000" required />}</Field>
              <Button type="submit" variant="primary" className="mt-5 w-full" icon={<UserPlus size={17} />} isLoading={isAssigning} disabled={!selectedCompanyId}>Assign operator</Button>
            </form>

            <div className="surface overflow-hidden">
              <div className="border-b border-[var(--line)] p-5 sm:p-6"><SectionHeader title="Operator memberships" description={selectedCompany ? `Access assignments for ${selectedCompany.name}.` : 'Select a company to inspect assignments.'} /></div>
              {membershipError ? <div className="p-5 text-sm font-semibold text-[var(--red)]" role="alert">{membershipError}</div> : memberships.length === 0 ? <EmptyState title="No operators assigned" description="Assign an operator user ID to give this company a station workspace." icon={<UsersRound size={23} />} /> : (
                <div className="divide-y divide-[var(--line)]">
                  {memberships.map((membership) => <div key={membership.membership_id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div><p className="font-data break-all text-sm font-bold">{membership.user_id}</p><p className="mt-1 text-xs text-[var(--steel)]">Assigned {formatDateTime(membership.assigned_at)}</p></div><Badge tone={membership.is_active ? 'success' : 'danger'}>{membership.is_active ? 'Active' : 'Inactive'}</Badge></div>)}
                </div>
              )}
            </div>
          </section>
        </>
      )}

      <Dialog open={Boolean(editingCompany)} onClose={() => setEditingCompany(null)} title="Edit company" description="Update the name used throughout the admin and operator workspaces." size="sm" preventClose={isEditing} footer={<><Button onClick={() => setEditingCompany(null)} disabled={isEditing}>Cancel</Button><Button type="submit" form="edit-company-form" variant="primary" isLoading={isEditing}>Save company</Button></>}>
        <form id="edit-company-form" onSubmit={handleEdit}><Field label="Company name">{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={editingName} onChange={(event) => setEditingName(event.target.value)} required autoFocus />}</Field></form>
      </Dialog>
    </div>
  );
}
