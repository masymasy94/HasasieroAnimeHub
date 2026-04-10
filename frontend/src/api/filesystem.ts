import type { BrowseResponse } from '../types/filesystem';
import { apiFetch } from './client';

export function browseFolder(path: string): Promise<BrowseResponse> {
  const params = new URLSearchParams({ path });
  return apiFetch<BrowseResponse>(`/filesystem/browse?${params}`);
}

export function getHighestEpisode(
  path: string,
  animeTitle = '',
): Promise<{ highest_episode: number; title_match: boolean }> {
  const params = new URLSearchParams({ path, anime_title: animeTitle });
  return apiFetch<{ highest_episode: number; title_match: boolean }>(
    `/filesystem/highest-episode?${params}`,
  );
}

export function createFolder(
  parentPath: string,
  name: string,
): Promise<BrowseResponse> {
  return apiFetch<BrowseResponse>('/filesystem/mkdir', {
    method: 'POST',
    body: JSON.stringify({ parent_path: parentPath, name }),
  });
}
