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

const CRON_PRESETS: { label: string; expr: string }[] = [
  { label: 'Ogni giorno 04:00', expr: '0 4 * * *' },
  { label: 'Ogni 6 ore', expr: '0 */6 * * *' },
  { label: 'Ogni 12 ore', expr: '0 */12 * * *' },
  { label: 'Ogni domenica 22:00', expr: '0 22 * * 0' },
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

  const { data, isLoading } = useQuery({
    queryKey: ['scheduled'],
    queryFn: listSchedules,
    refetchInterval: 30000,
  });

  // Sync cron input from server
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

  const handleSaveCron = async () => {
    if (!cronValid || !cronInput) return;
    setCronSaving(true);
    try {
      await setCron(cronInput);
      queryClient.invalidateQueries({ queryKey: ['scheduled'] });
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
  const cronChanged = data?.cron_expr !== cronInput;

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

      {/* Global cron config */}
      <div className="bg-bg-secondary border border-border rounded-[5px] p-4 space-y-2">
        <div className="flex items-center gap-2">
          <label className="text-[11px] text-text-secondary whitespace-nowrap">Controllo automatico (cron):</label>
          <input
            value={cronInput}
            onChange={(e) => setCronInput(e.target.value)}
            className={`w-40 px-2 py-1 text-xs font-mono bg-bg-card border rounded text-text-white ${
              cronValid ? 'border-border' : 'border-error'
            }`}
          />
          {cronChanged && cronValid && (
            <button
              onClick={handleSaveCron}
              disabled={cronSaving}
              className="px-2 py-1 text-[11px] bg-accent text-white rounded disabled:opacity-50"
            >
              {cronSaving ? 'Salvo...' : 'Salva'}
            </button>
          )}
          <span className="text-[11px] text-text-secondary">
            Prossimo: {formatDate(data?.next_run_at ?? null)}
          </span>
        </div>
        <div className="flex flex-wrap gap-1">
          {CRON_PRESETS.map((p) => (
            <button
              key={p.expr}
              onClick={() => setCronInput(p.expr)}
              className={`px-2 py-0.5 text-[10px] rounded border ${
                cronInput === p.expr
                  ? 'bg-accent/15 border-accent/30 text-accent'
                  : 'bg-bg-card border-border text-text-secondary hover:text-text-white'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {cronValid && cronNexts.length > 0 && (
          <div className="text-[10px] text-text-secondary">
            Prossime esecuzioni: {cronNexts.map((t) => new Date(t).toLocaleString()).join(' · ')}
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
                <h3 className="text-sm font-medium text-text-white truncate">
                  {s.anime_title}
                </h3>
                <div className="flex flex-wrap items-center gap-3 text-[11px] text-text-secondary mt-0.5">
                  <span className="px-1.5 py-0.5 bg-bg-card rounded text-[10px]">
                    {s.source_site}
                  </span>
                  <span>Cartella: /downloads/{s.dest_folder}</span>
                  <span>Ultimo check: {formatDate(s.last_run_at)}</span>
                  {s.last_error && (
                    <span className="text-error">Errore: {s.last_error}</span>
                  )}
                </div>
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
