import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createSchedule,
  deleteSchedule,
  listSchedules,
  runAllNow,
  runScheduleNow,
  setCron,
  updateSchedule,
  validateCron,
} from '../api/scheduled';
import { ScheduleForm } from '../components/ScheduleForm';
import type { ScheduleCreateRequest, ScheduledDownload } from '../types/scheduled';

const FREQUENCY_OPTIONS: { label: string; expr: string }[] = [
  { label: 'Ogni 6 ore', expr: '0 */6 * * *' },
  { label: 'Ogni 12 ore', expr: '0 */12 * * *' },
  { label: 'Ogni giorno alle 04:00', expr: '0 4 * * *' },
  { label: 'Ogni giorno alle 22:00', expr: '0 22 * * *' },
  { label: 'Ogni domenica alle 04:00', expr: '0 4 * * 0' },
];

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString();
}

export function ScheduledPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<ScheduledDownload | null>(null);
  const [showForm, setShowForm] = useState(false);

  // Cron state
  const [cronInput, setCronInput] = useState('');
  const [cronValid, setCronValid] = useState(true);
  const [cronNexts, setCronNexts] = useState<string[]>([]);
  const [cronSaving, setCronSaving] = useState(false);
  const [cronError, setCronError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['scheduled'],
    queryFn: listSchedules,
    refetchInterval: (query) => {
      const hasActive = query.state.data?.scheduled?.some(
        (s) => s.active_downloads.length > 0
      );
      return hasActive ? 3000 : 30000;
    },
  });

  // Sync cron input from server on load
  useEffect(() => {
    if (data?.cron_expr && cronInput === '') {
      setCronInput(data.cron_expr);
    }
  }, [data?.cron_expr]);

  // Validate cron debounce
  useEffect(() => {
    if (!cronInput) return;
    const timer = setTimeout(() => {
      validateCron(cronInput)
        .then((res) => {
          setCronValid(res.valid);
          setCronNexts(res.valid ? res.next_runs : []);
        })
        .catch(() => setCronValid(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [cronInput]);

  const saveCron = async (expr: string) => {
    setCronSaving(true);
    setCronError(null);
    try {
      await setCron(expr);
      queryClient.invalidateQueries({ queryKey: ['scheduled'] });
    } catch (e) {
      setCronError((e as Error).message);
    } finally {
      setCronSaving(false);
    }
  };

  const createMutation = useMutation({
    mutationFn: createSchedule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled'] });
      setShowForm(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, request }: { id: number; request: ScheduleCreateRequest }) =>
      updateSchedule(id, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled'] });
      setEditing(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSchedule,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scheduled'] }),
  });

  const runMutation = useMutation({
    mutationFn: runScheduleNow,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled'] });
      queryClient.invalidateQueries({ queryKey: ['downloads'] });
    },
  });

  const runAllMutation = useMutation({
    mutationFn: runAllNow,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled'] });
      queryClient.invalidateQueries({ queryKey: ['downloads'] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      updateSchedule(id, { enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scheduled'] }),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="inline-block w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  const schedules = data?.scheduled ?? [];
  const cronChanged = !!data?.cron_expr && data.cron_expr !== cronInput;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-white">Download Programmati</h1>
        <div className="flex items-center gap-2">
          {schedules.length > 0 && (
            <button
              onClick={() => runAllMutation.mutate()}
              disabled={runAllMutation.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded-[5px] bg-accent/10 text-accent hover:bg-accent hover:text-white disabled:opacity-50"
            >
              Esegui tutti ora
            </button>
          )}
          <button
            onClick={() => setShowForm(true)}
            className="px-3 py-1.5 text-xs font-medium bg-accent text-white rounded-[5px]"
          >
            + Nuovo
          </button>
        </div>
      </div>

      {/* Frequenza controllo */}
      <div className="bg-bg-secondary border border-border rounded-[5px] p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-accent flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm font-medium text-text-white">Frequenza controllo:</span>
          </div>

          {/* Dropdown — auto-salva alla selezione */}
          <select
            value={FREQUENCY_OPTIONS.find((o) => o.expr === cronInput) ? cronInput : '__custom__'}
            disabled={cronSaving}
            onChange={(e) => {
              if (e.target.value !== '__custom__') {
                setCronInput(e.target.value);
                saveCron(e.target.value);
              }
            }}
            className="px-2 py-1.5 text-xs bg-bg-card border border-border rounded text-text-white disabled:opacity-50"
          >
            {FREQUENCY_OPTIONS.map((o) => (
              <option key={o.expr} value={o.expr}>{o.label}</option>
            ))}
            {!FREQUENCY_OPTIONS.find((o) => o.expr === cronInput) && (
              <option value="__custom__">Personalizzato: {cronInput}</option>
            )}
          </select>

          {/* Input cron manuale */}
          <input
            value={cronInput}
            onChange={(e) => setCronInput(e.target.value)}
            title="Espressione cron"
            className={`w-32 px-2 py-1 text-[11px] font-mono bg-bg-card border rounded text-text-secondary ${
              cronValid ? 'border-border' : 'border-error'
            }`}
          />

          {/* Bottone salva per input manuale */}
          {cronChanged && cronValid && (
            <button
              onClick={() => saveCron(cronInput)}
              disabled={cronSaving}
              className="px-3 py-1 text-[11px] bg-accent text-white rounded disabled:opacity-50"
            >
              {cronSaving ? 'Salvo...' : 'Salva'}
            </button>
          )}

          {cronSaving && (
            <span className="text-[11px] text-accent">Salvando...</span>
          )}

          <div className="flex items-center gap-1.5 ml-auto">
            <svg className="w-3.5 h-3.5 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-xs text-text-white font-medium">
              Prossimo controllo: {formatDate(data?.next_run_at ?? null)}
            </span>
          </div>
        </div>

        {cronError && (
          <div className="mt-2 text-[11px] text-error">{cronError}</div>
        )}
        {cronValid && cronNexts.length > 0 && (
          <div className="mt-2 text-[10px] text-text-secondary">
            Prossime 3 esecuzioni: {cronNexts.map((t) => new Date(t).toLocaleString()).join(' · ')}
          </div>
        )}
      </div>

      {schedules.length === 0 ? (
        <div className="text-center py-16 text-text-secondary space-y-2">
          <p>Nessun download programmato.</p>
          <p className="text-sm">Clicca "Nuovo" per aggiungerne uno.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {schedules.map((s) => (
            <div
              key={s.id}
              className={`flex items-center gap-4 bg-bg-secondary border border-border rounded-[5px] p-4 ${
                !s.enabled ? 'opacity-50' : ''
              }`}
            >
              {s.cover_url && (
                <img
                  src={s.cover_url}
                  alt={s.anime_title}
                  className="w-12 h-16 object-cover rounded flex-shrink-0"
                />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-medium text-text-white truncate">
                    {s.anime_title}
                  </h3>
                  <span className="px-1.5 py-0.5 bg-accent/15 text-accent rounded text-[10px] font-medium flex-shrink-0">
                    EP {s.current_episode}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-[11px] text-text-secondary mt-0.5">
                  <span className="px-1.5 py-0.5 bg-bg-card rounded text-[10px]">
                    {s.source_site}
                  </span>
                  <span>/downloads/{s.dest_folder}</span>
                  <span>Ultimo check: {formatDate(s.last_run_at)}</span>
                  {s.last_error && (
                    <span className="text-error">Errore: {s.last_error}</span>
                  )}
                </div>
                {s.active_downloads.length > 0 && (
                  <div className="mt-1.5 space-y-1">
                    {s.active_downloads.map((dl) => (
                      <div key={dl.id} className="flex items-center gap-2">
                        <span className="text-[10px] text-text-secondary w-10 flex-shrink-0">
                          EP {dl.episode_number}
                        </span>
                        <div className="flex-1 h-1.5 bg-bg-card rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              dl.status === 'downloading' ? 'bg-accent' :
                              dl.status === 'finalizing' ? 'bg-warning' : 'bg-text-secondary'
                            }`}
                            style={{ width: `${Math.min(dl.progress, 100)}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-text-secondary w-12 text-right flex-shrink-0">
                          {dl.status === 'queued' ? 'in coda' :
                           dl.status === 'finalizing' ? 'finalizzando' :
                           `${dl.progress.toFixed(0)}%`}
                        </span>
                        {dl.speed_bps > 0 && (
                          <span className="text-[10px] text-text-secondary flex-shrink-0">
                            {(dl.speed_bps / 1024 / 1024).toFixed(1)} MB/s
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => runMutation.mutate(s.id)}
                  disabled={runMutation.isPending}
                  className="px-3 py-1.5 text-xs font-medium rounded-[5px] bg-accent/10 text-accent hover:bg-accent hover:text-white disabled:opacity-50"
                >
                  Esegui ora
                </button>
                <button
                  onClick={() => toggleMutation.mutate({ id: s.id, enabled: !s.enabled })}
                  className={`px-3 py-1.5 text-xs font-medium rounded-[5px] border ${
                    s.enabled
                      ? 'border-success/50 text-success hover:bg-success/10'
                      : 'border-border text-text-secondary hover:text-text-white'
                  }`}
                >
                  {s.enabled ? 'Attivo' : 'Disattivato'}
                </button>
                <button
                  onClick={() => setEditing(s)}
                  className="px-3 py-1.5 text-xs font-medium rounded-[5px] border border-border text-text-secondary hover:text-text-white"
                >
                  Modifica
                </button>
                <button
                  onClick={() => {
                    if (confirm(`Eliminare "${s.anime_title}"?`)) {
                      deleteMutation.mutate(s.id);
                    }
                  }}
                  className="px-3 py-1.5 text-xs font-medium rounded-[5px] bg-error/10 text-error hover:bg-error hover:text-white"
                >
                  Elimina
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <ScheduleForm
          onSubmit={async (req) => {
            await createMutation.mutateAsync(req);
          }}
          onCancel={() => setShowForm(false)}
        />
      )}
      {editing && (
        <ScheduleForm
          initial={editing}
          onSubmit={async (req) => {
            await updateMutation.mutateAsync({ id: editing.id, request: req });
          }}
          onCancel={() => setEditing(null)}
        />
      )}
    </div>
  );
}
