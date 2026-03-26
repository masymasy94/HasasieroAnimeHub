import type { AnimeSearchResult, SearchResponse } from '../types/anime';
import { apiFetch } from './client';

const BASE_URL = '/api';

/**
 * Stream search results via SSE. Calls `onResults` each time a provider responds.
 * Returns an abort function to cancel the stream.
 */
export function streamSearch(
  title: string,
  onResults: (site: string, results: AnimeSearchResult[]) => void,
  onDone: () => void,
  onError: (error: Error) => void,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(
        `${BASE_URL}/search?title=${encodeURIComponent(title)}`,
        { signal: controller.signal },
      );

      if (!response.ok) {
        throw new Error(`Search failed: ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse complete SSE events from the buffer
        const parts = buffer.split('\n\n');
        buffer = parts.pop()!; // keep incomplete part

        for (const part of parts) {
          if (!part.trim()) continue;

          let eventType = 'message';
          let data = '';

          for (const line of part.split('\n')) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7);
            } else if (line.startsWith('data: ')) {
              data = line.slice(6);
            }
          }

          if (eventType === 'results' && data) {
            const parsed = JSON.parse(data);
            onResults(parsed.source_site, parsed.results);
          } else if (eventType === 'done') {
            onDone();
          }
        }
      }

      // Handle any remaining buffer
      if (buffer.trim()) {
        for (const line of buffer.split('\n')) {
          if (line.startsWith('data: ')) {
            // last event
          }
        }
      }

      onDone();
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      onError(err instanceof Error ? err : new Error(String(err)));
    }
  })();

  return () => controller.abort();
}

export function getLatestAnime(): Promise<SearchResponse> {
  return apiFetch<SearchResponse>('/latest');
}
