import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getDownloads, cancelAllDownloads, clearCompletedDownloads, retryAllFailed, pauseAllDownloads, resumeAllDownloads, getDiskUsage } from '../api/downloads';
import { DownloadItem } from '../components/DownloadItem';

type Tab = 'all' | 'active' | 'completed' | 'failed';

const TAB_FILTERS: Record<Tab, string[] | undefined> = {
  all: undefined,
  active: ['queued', 'downloading', 'finalizing', 'paused'],
  completed: ['completed'],
  failed: ['failed', 'cancelled'],
};

const TABS: { key: Tab; label: string }[] = [
  { key: 'all', label: 'Tutti' },
  { key: 'active', label: 'Attivi' },
  { key: 'completed', label: 'Completati' },
  { key: 'failed', label: 'Falliti' },
];

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / k ** i).toFixed(1)} ${sizes[i]}`;
}

export function DownloadsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('all');
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['downloads', activeTab],
    queryFn: () => getDownloads(TAB_FILTERS[activeTab]),
    refetchInterval: (query) => {
      // Poll faster when there are active downloads, slower otherwise
      const downloads = query.state.data?.downloads;
      const hasActive = downloads?.some(
        (d) => d.status === 'downloading' || d.status === 'queued' || d.status === 'finalizing',
      );
      return hasActive ? 5000 : 30000;
    },
  });

  const { data: disk } = useQuery({
    queryKey: ['disk-usage'],
    queryFn: getDiskUsage,
    refetchInterval: 10000,
  });

  const hasActive = data?.downloads?.some(
    (d) => d.status === 'downloading' || d.status === 'queued' || d.status === 'finalizing',
  );

  const hasFinished = data?.downloads?.some(
    (d) => d.status === 'completed' || d.status === 'failed' || d.status === 'cancelled',
  );

  const hasFailed = data?.downloads?.some((d) => d.status === 'failed');

  const hasPausable = data?.downloads?.some(
    (d) => d.status === 'downloading' || d.status === 'queued',
  );

  const hasPaused = data?.downloads?.some((d) => d.status === 'paused');

  const handleCancelAll = async () => {
    await cancelAllDownloads();
    queryClient.invalidateQueries({ queryKey: ['downloads'] });
  };

  const handlePauseAll = async () => {
    await pauseAllDownloads();
    queryClient.invalidateQueries({ queryKey: ['downloads'] });
  };

  const handleResumeAll = async () => {
    await resumeAllDownloads();
    queryClient.invalidateQueries({ queryKey: ['downloads'] });
  };

  const handleClearCompleted = async () => {
    await clearCompletedDownloads();
    queryClient.invalidateQueries({ queryKey: ['downloads'] });
  };

  const handleRetryAllFailed = async () => {
    await retryAllFailed();
    queryClient.invalidateQueries({ queryKey: ['downloads'] });
  };

  const usedPercent = disk ? (disk.used_bytes / disk.total_bytes) * 100 : 0;
  const diskWarning = disk ? disk.free_bytes < 5 * 1024 * 1024 * 1024 : false; // < 5GB

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-white">Downloads</h1>
        <div className="flex gap-2">
          {hasFailed && (
            <button
              onClick={handleRetryAllFailed}
              className="px-4 py-2 text-xs font-medium rounded-[5px] bg-accent/10 text-accent hover:bg-accent hover:text-white transition-colors"
            >
              Ritenta tutti
            </button>
          )}
          {hasFinished && (
            <button
              onClick={handleClearCompleted}
              className="px-4 py-2 text-xs font-medium rounded-[5px] bg-bg-secondary text-text-secondary hover:text-text-white border border-border hover:bg-bg-hover transition-colors"
            >
              Pulisci lista
            </button>
          )}
          {hasPaused && (
            <button
              onClick={handleResumeAll}
              className="px-4 py-2 text-xs font-medium rounded-[5px] bg-accent/10 text-accent hover:bg-accent hover:text-white transition-colors"
            >
              Riprendi tutti
            </button>
          )}
          {hasPausable && (
            <button
              onClick={handlePauseAll}
              className="px-4 py-2 text-xs font-medium rounded-[5px] bg-warning/10 text-warning hover:bg-warning hover:text-black transition-colors"
            >
              Pausa tutti
            </button>
          )}
          {hasActive && (
            <button
              onClick={handleCancelAll}
              className="px-4 py-2 text-xs font-medium rounded-[5px] bg-error/10 text-error hover:bg-error hover:text-white transition-colors"
            >
              Annulla tutti
            </button>
          )}
        </div>
      </div>

      {/* Disk usage */}
      {disk && disk.total_bytes > 0 && (
        <div className="bg-bg-secondary border border-border rounded-[5px] p-4 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-text-secondary">
              Spazio disco: {formatBytes(disk.used_bytes)} / {formatBytes(disk.total_bytes)}
            </span>
            <span className={`font-medium ${diskWarning ? 'text-warning' : 'text-text-secondary'}`}>
              {formatBytes(disk.free_bytes)} liberi
            </span>
          </div>
          <div className="w-full bg-bg-primary rounded-full h-2 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                usedPercent > 90 ? 'bg-error' : usedPercent > 75 ? 'bg-warning' : 'bg-accent'
              }`}
              style={{ width: `${Math.min(100, usedPercent)}%` }}
            />
          </div>
          {diskWarning && (
            <p className="text-[11px] text-warning">
              Spazio disco in esaurimento. Libera spazio per continuare a scaricare.
            </p>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-bg-secondary p-1 rounded-[5px] border border-border">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex-1 py-2 text-sm font-medium rounded-[5px] transition-colors ${
              activeTab === key
                ? 'bg-accent text-white'
                : 'text-text-secondary hover:text-text-white hover:bg-bg-hover'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Download list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-10">
          <span className="inline-block w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        </div>
      ) : data?.downloads && data.downloads.length > 0 ? (
        <div className="space-y-3">
          {data.downloads.map((dl) => (
            <DownloadItem key={dl.id} download={dl} />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-text-secondary">
          Nessun download
        </div>
      )}
    </div>
  );
}
