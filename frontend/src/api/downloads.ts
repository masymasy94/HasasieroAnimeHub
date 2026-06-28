import type { DownloadRequest, DownloadsResponse } from '../types/download';
import { apiFetch } from './client';

export function startDownloads(request: DownloadRequest): Promise<DownloadsResponse> {
  return apiFetch<DownloadsResponse>('/downloads', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export function getDownloads(statuses?: string[]): Promise<DownloadsResponse> {
  const params = statuses?.map(s => `status=${s}`).join('&');
  return apiFetch<DownloadsResponse>(`/downloads${params ? `?${params}` : ''}`);
}

export function cancelDownload(id: number): Promise<void> {
  return apiFetch<void>(`/downloads/${id}`, { method: 'DELETE' });
}

export function cancelAllDownloads(): Promise<{ cancelled: number }> {
  return apiFetch<{ cancelled: number }>('/downloads/cancel-all', { method: 'POST' });
}

export function clearCompletedDownloads(): Promise<{ cleared: number }> {
  return apiFetch<{ cleared: number }>('/downloads/clear-completed', { method: 'POST' });
}

export function retryDownload(id: number): Promise<void> {
  return apiFetch<void>(`/downloads/${id}/retry`, { method: 'POST' });
}

export function retryAllFailed(): Promise<{ retried: number }> {
  return apiFetch<{ retried: number }>('/downloads/retry-all-failed', { method: 'POST' });
}

export function pauseDownload(id: number): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/downloads/${id}/pause`, { method: 'POST' });
}

export function resumeDownload(id: number): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/downloads/${id}/resume`, { method: 'POST' });
}

export function pauseAllDownloads(): Promise<{ paused: number }> {
  return apiFetch<{ paused: number }>('/downloads/pause-all', { method: 'POST' });
}

export function resumeAllDownloads(): Promise<{ resumed: number }> {
  return apiFetch<{ resumed: number }>('/downloads/resume-all', { method: 'POST' });
}

export interface DiskUsage {
  total_bytes: number;
  used_bytes: number;
  free_bytes: number;
  path: string;
  host_path: string;
}

export function getDiskUsage(): Promise<DiskUsage> {
  return apiFetch<DiskUsage>('/disk-usage');
}
