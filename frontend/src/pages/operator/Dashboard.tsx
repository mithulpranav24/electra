import { useCallback, useEffect, useMemo, useState } from 'react';
import { Building2, CircleOff, MapPin, Pencil, PlugZap, Plus, RadioTower, Trash2, Wrench } from 'lucide-react';
import { authService, operatorService } from '../../services/api';
import type { ChargingPort, CompanyMembership, Station } from '../../types';
import { getErrorMessage } from '../../lib/errors';
import { formatCurrency, shortId } from '../../lib/format';
import { PortFormDialog } from '../../components/operator/PortFormDialog';
import { StationFormDialog } from '../../components/operator/StationFormDialog';
import { Badge } from '../../ui/Badge';
import { statusTone } from '../../lib/status';
import { Button, IconButton } from '../../ui/Button';
import { ConfirmDialog } from '../../ui/ConfirmDialog';
import { EmptyState, ErrorState, LoadingState } from '../../ui/Feedback';
import { PageHeader, SectionHeader } from '../../ui/Page';
import { useToast } from '../../ui/ToastContext';

type DeleteTarget = { kind: 'station'; station: Station } | { kind: 'port'; port: ChargingPort; stationName: string };

export default function OperatorDashboard() {
  const [memberships, setMemberships] = useState<CompanyMembership[]>([]);
  const [companyId, setCompanyId] = useState('');
  const [stations, setStations] = useState<Station[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [stationDialog, setStationDialog] = useState<{ open: boolean; station: Station | null }>({ open: false, station: null });
  const [portDialog, setPortDialog] = useState<{ open: boolean; stationId: string; port: ChargingPort | null }>({ open: false, stationId: '', port: null });
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const { pushToast } = useToast();

  const loadStations = useCallback(async (targetCompanyId: string, showLoader = true) => {
    if (showLoader) setIsLoading(true);
    setError('');
    try {
      setStations(await operatorService.getStations(targetCompanyId));
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Stations could not be loaded for this company.'));
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
      if (firstCompanyId) await loadStations(firstCompanyId, false);
      else setStations([]);
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Your operator assignments could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }, [loadStations]);

  useEffect(() => { void loadWorkspace(); }, [loadWorkspace]);

  const metrics = useMemo(() => {
    const ports = stations.flatMap((station) => station.ports ?? []);
    return {
      activeStations: stations.filter((station) => station.is_active).length,
      available: ports.filter((port) => port.is_active && port.status === 'Available' && !port.is_pending_maintenance).length,
      charging: ports.filter((port) => port.status === 'Charging').length,
      attention: ports.filter((port) => port.has_health_warning || port.has_blocked_warning || port.is_pending_maintenance || ['Maintenance', 'Offline'].includes(port.status)).length,
    };
  }, [stations]);

  const refresh = () => companyId ? loadStations(companyId, false) : loadWorkspace();

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      if (deleteTarget.kind === 'station') await operatorService.deleteStation(deleteTarget.station.station_id);
      else await operatorService.deletePort(deleteTarget.port.port_id);
      const kind = deleteTarget.kind;
      setDeleteTarget(null);
      await refresh();
      pushToast({ title: kind === 'station' ? 'Station deactivated' : 'Port removed', message: 'Historical records remain preserved by the backend.', tone: 'success' });
    } catch (deleteError) {
      pushToast({ title: 'Couldn’t complete the removal', message: getErrorMessage(deleteError, 'Active reservations, sessions, or queue activity may need to drain first.'), tone: 'error' });
    } finally {
      setIsDeleting(false);
    }
  };

  const deleteName = deleteTarget?.kind === 'station' ? deleteTarget.station.name : deleteTarget?.kind === 'port' ? `port ${deleteTarget.port.qr_code}` : 'this item';

  return (
    <div className="flex flex-col gap-7 enter-up">
      <PageHeader eyebrow="Operator workspace" title="Station operations" description="Keep stations bookable, port states accurate, and warnings visible to drivers." actions={<><Button icon={<PlugZap size={18} />} onClick={() => setPortDialog({ open: true, stationId: '', port: null })} disabled={!companyId || stations.length === 0}>Add port</Button><Button variant="primary" icon={<Plus size={18} />} onClick={() => setStationDialog({ open: true, station: null })} disabled={!companyId}>Create station</Button></>} />

      {memberships.length > 1 && (
        <div className="surface flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div><p className="text-sm font-bold">Company assignment</p><p className="text-xs text-[var(--steel)]">Switch between companies assigned to your operator account.</p></div>
          <select className="field-control sm:max-w-sm" value={companyId} onChange={(event) => { const id = event.target.value; setCompanyId(id); void loadStations(id); }} aria-label="Select company assignment">{memberships.map((membership) => <option key={membership.membership_id} value={membership.company_id}>Company {shortId(membership.company_id, 12)}</option>)}</select>
        </div>
      )}

      {isLoading ? <div className="surface"><LoadingState label="Loading station operations" /></div> : error && stations.length === 0 ? <ErrorState description={error} onRetry={() => void loadWorkspace()} /> : !companyId ? (
        <div className="surface"><EmptyState title="No company assignment" description="An administrator must assign your operator account to a company before you can manage stations." icon={<Building2 size={24} />} /></div>
      ) : (
        <>
          {error && <div className="rounded-xl border border-[var(--red)]/25 bg-[var(--red-soft)] p-4 text-sm font-semibold text-[var(--red-dark)]" role="alert">{error}</div>}

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Operations overview">
            {[
              { label: 'Active stations', value: metrics.activeStations, icon: MapPin, tone: 'bg-[var(--blue-soft)] text-[#285270]' },
              { label: 'Ports available', value: metrics.available, icon: PlugZap, tone: 'bg-[var(--teal-soft)] text-[var(--teal-dark)]' },
              { label: 'Charging now', value: metrics.charging, icon: RadioTower, tone: 'bg-[var(--amber-soft)] text-[#6f500c]' },
              { label: 'Needs attention', value: metrics.attention, icon: Wrench, tone: metrics.attention ? 'bg-[var(--red-soft)] text-[var(--red)]' : 'bg-[var(--paper-muted)] text-[var(--steel)]' },
            ].map(({ label, value, icon: Icon, tone }) => <div key={label} className="surface flex items-center gap-4 p-4"><span className={`flex size-11 items-center justify-center rounded-full ${tone}`}><Icon size={20} /></span><div><p className="font-data text-2xl font-bold">{value}</p><p className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">{label}</p></div></div>)}
          </section>

          <section className="surface overflow-hidden">
            <div className="flex flex-col gap-3 border-b border-[var(--line)] p-5 sm:flex-row sm:items-start sm:justify-between sm:p-6"><SectionHeader title="Stations" description={`Company ${shortId(companyId, 12)} · ${stations.length} station${stations.length === 1 ? '' : 's'}`} /><Button size="sm" variant="ghost" onClick={() => void refresh()}>Refresh</Button></div>
            {stations.length === 0 ? (
              <EmptyState title="Create the first station" description="Add its location, pricing, and operating hours, then attach charging ports." icon={<MapPin size={23} />} action={<Button variant="primary" icon={<Plus size={17} />} onClick={() => setStationDialog({ open: true, station: null })}>Create station</Button>} />
            ) : (
              <div className="divide-y divide-[var(--line)]">
                {stations.map((station) => (
                  <article key={station.station_id} className={!station.is_active ? 'bg-[var(--paper-muted)] opacity-75' : ''}>
                    <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start sm:justify-between sm:p-6">
                      <div className="min-w-0">
                        <div className="mb-2 flex flex-wrap items-center gap-2"><h3 className="font-display text-xl font-bold">{station.name}</h3><Badge tone={station.is_active ? 'success' : 'danger'}>{station.is_active ? 'Active' : 'Inactive'}</Badge>{station.is_deprecating && <Badge tone="warning">Deprecating</Badge>}{station.locked_gate && <Badge tone="info">Locked gate</Badge>}</div>
                        <p className="font-data text-xs text-[var(--steel)]">{station.lat.toFixed(4)}, {station.lng.toFixed(4)} · {station.timezone}</p>
                        <p className="mt-2 text-sm text-[var(--steel-dark)]">{formatCurrency(station.price_per_kwh)}/kWh · Minimum {formatCurrency(station.minimum_session_fee)} · {station.opening_time_local && station.closing_time_local ? `${station.opening_time_local.slice(0, 5)}–${station.closing_time_local.slice(0, 5)}` : '24 hours'}</p>
                      </div>
                      <div className="flex gap-2"><Button size="sm" icon={<Plus size={16} />} onClick={() => setPortDialog({ open: true, stationId: station.station_id, port: null })} disabled={!station.is_active}>Add port</Button><IconButton label={`Edit ${station.name}`} onClick={() => setStationDialog({ open: true, station })}><Pencil size={17} /></IconButton><IconButton label={`Deactivate ${station.name}`} variant="danger" onClick={() => setDeleteTarget({ kind: 'station', station })} disabled={!station.is_active}><Trash2 size={17} /></IconButton></div>
                    </div>

                    <div className="border-t border-[var(--line)] bg-[#fafbfa] p-4 sm:p-5">
                      {station.ports?.length ? (
                        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                          {station.ports.map((port) => {
                            const warning = port.has_health_warning || port.has_blocked_warning || port.is_pending_maintenance;
                            return (
                              <div key={port.port_id} className="rounded-[var(--radius-md)] border border-[var(--line)] bg-white p-4">
                                <div className="flex items-start justify-between gap-3"><div><p className="font-display font-bold">{port.connector_type} · {port.charger_type}</p><p className="font-data mt-1 truncate text-xs text-[var(--steel)]" title={port.qr_code}>QR {port.qr_code}</p></div><Badge tone={statusTone(port.status)}>{port.status}</Badge></div>
                                {warning && <div className="mt-3 flex flex-wrap gap-1.5">{port.has_health_warning && <Badge tone="warning">Health warning</Badge>}{port.has_blocked_warning && <Badge tone="warning">Blocked bay</Badge>}{port.is_pending_maintenance && <Badge tone="danger">Pending maintenance</Badge>}</div>}
                                <div className="mt-4 flex justify-end gap-2"><IconButton label={`Edit port ${port.qr_code}`} onClick={() => setPortDialog({ open: true, stationId: station.station_id, port })}><Pencil size={16} /></IconButton><IconButton label={`Remove port ${port.qr_code}`} variant="danger" onClick={() => setDeleteTarget({ kind: 'port', port, stationName: station.name })} disabled={!port.is_active}><Trash2 size={16} /></IconButton></div>
                              </div>
                            );
                          })}
                        </div>
                      ) : <EmptyState compact title="No charging ports" description="Add a physical port to make this station useful to drivers." icon={<CircleOff size={21} />} action={<Button size="sm" icon={<Plus size={16} />} onClick={() => setPortDialog({ open: true, stationId: station.station_id, port: null })}>Add port</Button>} />}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}

      <StationFormDialog open={stationDialog.open} companyId={companyId} station={stationDialog.station} onClose={() => setStationDialog({ open: false, station: null })} onSuccess={(_station, mode) => { setStationDialog({ open: false, station: null }); void refresh(); pushToast({ title: mode === 'created' ? 'Station created' : 'Station updated', tone: 'success' }); }} />
      <PortFormDialog open={portDialog.open} stations={stations} stationId={portDialog.stationId} port={portDialog.port} onClose={() => setPortDialog({ open: false, stationId: '', port: null })} onSuccess={(_port, mode) => { setPortDialog({ open: false, stationId: '', port: null }); void refresh(); pushToast({ title: mode === 'created' ? 'Charging port added' : 'Charging port updated', tone: 'success' }); }} />
      <ConfirmDialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} onConfirm={() => void handleDelete()} title={`Remove ${deleteName}?`} description={<><strong>{deleteName}</strong> will be marked inactive rather than erased. The backend may reject this action while reservations, charging, or waitlist work is still active.</>} confirmLabel={deleteTarget?.kind === 'station' ? 'Deactivate station' : 'Remove port'} isLoading={isDeleting} />
    </div>
  );
}
