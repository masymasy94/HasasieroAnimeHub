import { useState } from 'react';
import type { DownloadStatus } from '../types/download';
import { useDownloadStore } from '../stores/downloadStore';
import { ProgressBar } from './ProgressBar';
import { cancelDownload, retryDownload, pauseDownload, resumeDownload } from '../api/downloads';
import { useQueryClient } from '@tanstack/react-query';

interface DownloadItemProps {
  download: DownloadStatus;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / k ** i).toFixed(1)} ${sizes[i]}`;
}

function formatSpeed(bps: number): string {
  if (bps === 0) return '';
  return `${formatBytes(bps)}/s`;
}

function getDirectoryPath(filePath: string): string {
  const parts = filePath.replace(/\\/g, '/').split('/');
  parts.pop();
  return parts.join('/');
}

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  queued: { label: 'In coda', className: 'text-warning' },
  downloading: { label: 'Download', className: 'text-accent' },
  finalizing: { label: 'Spostamento su NAS', className: 'text-accent' },
  completed: { label: 'Completato', className: 'text-success' },
  failed: { label: 'Fallito', className: 'text-error' },
  cancelled: { label: 'Annullato', className: 'text-text-secondary' },
  paused: { label: 'In pausa', className: 'text-warning' },
};

export function DownloadItem({ download }: DownloadItemProps) {
  const queryClient = useQueryClient();
  const wsProgress = useDownloadStore((s) => s.getProgress(download.id));
  const [copied, setCopied] = useState(false);

  const progress = wsProgress?.progress ?? download.progress;
  const speed = wsProgress?.speed_bps ?? download.speed_bps;
  const downloadedBytes = wsProgress?.downloaded_bytes ?? download.downloaded_bytes;
  const totalBytes = wsProgress?.total_bytes ?? download.total_bytes;

  const statusConfig = STATUS_CONFIG[download.status] ?? STATUS_CONFIG.queued;
  const isActive = download.status === 'downloading' || download.status === 'queued';
  const isFinalizing = download.status === 'finalizing';
  const isPaused = download.status === 'paused';

  const hostPath = download.host_file_path || download.file_path;
  const dirPath = hostPath ? getDirectoryPath(hostPath) : null;

  const handleCancel = async () => {
    await cancelDownload(download.id);
    queryClient.invalidateQueries({ queryKey: ['downloads'] });
  };

  const handleRetry = async () => {
    await retryDownload(download.id);
    queryClient.invalidateQueries({ queryKey: ['downloads'] });
  };

  const handlePause = async () => {
    await pauseDownload(download.id);
    queryClient.invalidateQueries({ queryKey: ['downloads'] });
  };

  const handleResume = async () => {
    await resumeDownload(download.id);
    queryClient.invalidateQueries({ queryKey: ['downloads'] });
  };

  const handleCopyPath = async () => {
    if (!dirPath) return;
    try {
      await navigator.clipboard.writeText(dirPath);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      prompt('Copia il percorso:', dirPath);
    }
  };

  return (
    <div className="bg-bg-secondary border border-border rounded-[5px] p-4 space-y-2">
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-medium truncate">{download.anime_title}</h4>
          <p className="text-xs text-text-secondary">
            Episodio {download.episode_number}
          </p>
        </div>
        <div className="flex items-center gap-2 ml-3">
          <span className={`text-xs font-medium ${statusConfig.className}`}>
            {statusConfig.label}
          </span>
          {download.status === 'completed' && download.file_exists && (
            <a
              href={`/api/downloads/${download.id}/file`}
              download
              title="Salva file"
              className="p-1.5 rounded bg-accent/10 text-accent hover:bg-accent hover:text-white transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </a>
          )}
          {download.status === 'completed' && !download.file_exists && (
            <span
              title="File non trovato sul disco"
              className="p-1.5 rounded bg-warning/10 text-warning"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </span>
          )}
          {isActive && (
            <button
              onClick={handlePause}
              className="text-xs px-2 py-1 rounded bg-warning/10 text-warning hover:bg-warning hover:text-black transition-colors"
            >
              Pausa
            </button>
          )}
          {isPaused && (
            <button
              onClick={handleResume}
              className="text-xs px-2 py-1 rounded bg-accent/10 text-accent hover:bg-accent hover:text-white transition-colors"
            >
              Riprendi
            </button>
          )}
          {(isActive || isPaused) && (
            <button
              onClick={handleCancel}
              className="text-xs px-2 py-1 rounded bg-error/10 text-error hover:bg-error hover:text-white transition-colors"
            >
              Annulla
            </button>
          )}
          {(download.status === 'failed' || download.status === 'cancelled') && (
            <button
              onClick={handleRetry}
              className="text-xs px-2 py-1 rounded bg-accent/10 text-accent hover:bg-accent hover:text-white transition-colors"
            >
              Riprova
            </button>
          )}
        </div>
      </div>

      {download.status === 'downloading' && (
        <>
          <ProgressBar progress={progress} />
          <div className="flex justify-between text-xs text-text-secondary">
            <span>
              {formatBytes(downloadedBytes)}
              {totalBytes > 0 && ` / ${formatBytes(totalBytes)}`}
            </span>
            <div className="flex gap-3">
              {speed > 0 && <span>{formatSpeed(speed)}</span>}
              <span>{progress.toFixed(1)}%</span>
            </div>
          </div>
        </>
      )}

      {isPaused && (
        <>
          <ProgressBar progress={progress} />
          <div className="flex justify-between text-xs text-text-secondary">
            <span>
              {formatBytes(downloadedBytes)}
              {totalBytes > 0 && ` / ${formatBytes(totalBytes)}`}
            </span>
            <span>{progress.toFixed(1)}% — in pausa</span>
          </div>
        </>
      )}

      {isFinalizing && (
        <div className="flex items-center gap-2 text-xs text-accent">
          <span className="inline-block w-3 h-3 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
          <span>Spostamento file su NAS in corso...</span>
        </div>
      )}

      {/* File path + copy feedback for completed downloads */}
      {download.status === 'completed' && hostPath && (
        <div className="flex items-center gap-1.5">
          {download.file_exists ? (
            <button
              onClick={handleCopyPath}
              className="text-text-secondary hover:text-accent transition-colors flex-shrink-0"
              title="Copia percorso"
            >
              {copied ? (
                <svg className="w-3.5 h-3.5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </button>
          ) : (
            <svg className="w-3.5 h-3.5 text-warning flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          )}
          <p className={`text-[11px] font-mono truncate ${download.file_exists ? 'text-text-secondary' : 'text-warning'}`} title={hostPath}>
            {copied ? <span className="text-success">Copiato!</span> : download.file_exists ? hostPath : `File non trovato: ${hostPath}`}
          </p>
        </div>
      )}

      {download.status === 'failed' && (
        <div className="flex items-center gap-2">
          {download.error_message && (
            <p className="text-xs text-error/80 truncate flex-1" title={download.error_message}>
              {download.error_message}
            </p>
          )}
          {download.retry_count > 0 && (
            <span className="text-[11px] text-text-secondary flex-shrink-0">
              {download.retry_count}/{download.max_retries} tentativi
            </span>
          )}
        </div>
      )}
    </div>
  );
}
