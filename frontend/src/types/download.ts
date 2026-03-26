export interface DownloadStatus {
  id: number;
  anime_id: number;
  anime_title: string;
  anime_slug: string;
  episode_id: number;
  episode_number: string;
  episode_title: string | null;
  status: 'queued' | 'downloading' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  downloaded_bytes: number;
  total_bytes: number;
  speed_bps: number;
  file_path: string | null;
  host_file_path: string | null;
  file_exists: boolean;
  retry_count: number;
  max_retries: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface DownloadRequest {
  anime_id: number;
  anime_title: string;
  anime_slug: string;
  cover_url: string | null;
  genres: string[];
  plot: string | null;
  year: string | null;
  source_site?: string;
  episodes: { episode_id: number; episode_number: string; episode_title?: string | null }[];
}

export interface DownloadsResponse {
  downloads: DownloadStatus[];
}

export interface WsProgressMessage {
  type: 'progress';
  download_id: number;
  progress: number;
  downloaded_bytes: number;
  total_bytes: number;
  speed_bps: number;
}

export interface WsStatusMessage {
  type: 'status_change';
  download_id: number;
  status: string;
  file_path?: string;
  completed_at?: string;
}

export interface WsErrorMessage {
  type: 'error';
  download_id: number;
  status: string;
  error_message: string;
}

export type WsMessage = WsProgressMessage | WsStatusMessage | WsErrorMessage;
