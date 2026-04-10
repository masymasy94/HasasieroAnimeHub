export type PatternType = 'preset' | 'custom';

export interface ActiveDownload {
  id: number;
  episode_number: string;
  status: string;
  progress: number;
  speed_bps: number;
}

export interface ScheduledDownload {
  id: number;
  anime_id: number;
  anime_slug: string;
  anime_title: string;
  cover_url: string | null;
  source_site: string;
  dest_folder: string;
  filename_template: string;
  filename_template_type: PatternType;
  enabled: boolean;
  last_run_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  current_episode: number;
  active_downloads: ActiveDownload[];
}

export interface ScheduleCreateRequest {
  anime_id: number;
  anime_slug: string;
  anime_title: string;
  cover_url?: string | null;
  source_site: string;
  dest_folder: string;
  filename_template: string;
  filename_template_type: PatternType;
  enabled?: boolean;
}

export interface ScheduleUpdateRequest {
  dest_folder?: string;
  filename_template?: string;
  filename_template_type?: PatternType;
  enabled?: boolean;
}

export interface ScheduleListResponse {
  scheduled: ScheduledDownload[];
  cron_expr: string;
  next_run_at: string | null;
}

export interface CronValidationResponse {
  valid: boolean;
  next_runs: string[];
  error: string | null;
}

export interface RunNowResponse {
  enqueued_episodes: number;
  skipped_reason: string | null;
}

export const PATTERN_PRESETS: { id: string; label: string; template: string }[] = [
  {
    id: 'plex_default',
    label: 'Plex (Show - S01E001 - Titolo)',
    template: '{anime} - S{season}E{episode} - {ep_title}.{ext}',
  },
  {
    id: 'episode_only',
    label: 'Solo episodio (0006.mp4)',
    template: '{episode}.{ext}',
  },
  {
    id: 'anime_and_episode',
    label: 'Anime + episodio (Show - 0006.mp4)',
    template: '{anime} - {episode}.{ext}',
  },
];
