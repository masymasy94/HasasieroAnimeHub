import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createSchedule,
  deleteSchedule,
  listSchedules,
  runScheduleNow,
  updateSchedule,
} from '../api/scheduled';
import { ScheduleForm } from '../components/ScheduleForm';
import type { ScheduleCreateRequest, ScheduledDownload } from '../types/scheduled';

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString();
}

export function ScheduledPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<ScheduledDownload | null>(null);
  const [showForm, setShowForm] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['scheduled'],
    queryFn: listSchedules,
    refetchInterval: 30000,
  });

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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-white">Download Programmati</h1>
        <button
          onClick={() => setShowForm(true)}
          className="px-3 py-1.5 text-xs font-medium bg-accent text-white rounded-[5px]"
        >
          + Nuovo
        </button>
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
                  <span>Cron: <code>{s.cron_expr}</code></span>
                  <span>Prossimo: {formatDate(s.next_run_at)}</span>
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
