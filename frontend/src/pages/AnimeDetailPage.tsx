import { useState, useCallback, useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { getAnimeDetail, getEpisodes, getStreamSource } from '../api/anime';
import { startDownloads } from '../api/downloads';
import { createSchedule } from '../api/scheduled';
import { checkTrackedStatus, trackAnime, untrackAnime } from '../api/tracked';
import { EpisodeList } from '../components/EpisodeList';
import { FolderBrowser } from '../components/FolderBrowser';
import { ScheduleForm } from '../components/ScheduleForm';
import { VideoPlayer } from '../components/VideoPlayer';
import type { AnimeSearchResult, Episode } from '../types/anime';

export function AnimeDetailPage() {
  const { animePath } = useParams<{ animePath: string }>();
  const [searchParams] = useSearchParams();
  const site = searchParams.get('site') || 'animeunity';
  const queryClient = useQueryClient();
  const [episodeEnd, setEpisodeEnd] = useState(120);
  const [streamInfo, setStreamInfo] = useState<{ url: string; type: 'mp4' | 'm3u8'; title: string } | null>(null);
  const [currentEpisode, setCurrentEpisode] = useState<Episode | null>(null);
  const [showFolderBrowser, setShowFolderBrowser] = useState(false);
  const [pendingDownload, setPendingDownload] = useState<((folder: string) => void) | null>(null);
  const [showScheduleForm, setShowScheduleForm] = useState(false);

  // Ask for the destination folder, then run the given download action with it
  const withFolder = useCallback((action: (folder: string) => void) => {
    setPendingDownload(() => action);
    setShowFolderBrowser(true);
  }, []);

  // Parse anime path
  const match = animePath?.match(/^(\d+)-(.+)$/);
  const animeId = match ? parseInt(match[1]) : 0;
  const slug = match ? match[2] : '';

  const { data: anime, isLoading: animeLoading } = useQuery({
    queryKey: ['anime', animeId, slug, site],
    queryFn: () => getAnimeDetail(animeId, slug, site),
    enabled: !!animeId,
  });

  const {
    data: episodesData,
    isLoading: episodesLoading,
    isFetching: episodesFetching,
  } = useQuery({
    queryKey: ['episodes', animeId, slug, episodeEnd, site],
    queryFn: () => getEpisodes(animeId, slug, 1, episodeEnd, site),
    enabled: !!animeId,
  });

  const { data: trackedStatus } = useQuery({
    queryKey: ['tracked-status', animeId, site],
    queryFn: () => checkTrackedStatus(animeId, site),
    enabled: !!animeId,
  });

  const trackMutation = useMutation({
    mutationFn: () => {
      if (!anime) throw new Error('No anime');
      return trackAnime({
        anime_id: anime.id,
        anime_slug: anime.slug,
        anime_title: anime.title,
        cover_url: anime.cover_url,
        genres: anime.genres,
        plot: anime.plot,
        year: anime.year,
        source_site: site,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tracked-status'] });
      queryClient.invalidateQueries({ queryKey: ['tracked'] });
    },
  });

  const untrackMutation = useMutation({
    mutationFn: () => {
      if (!trackedStatus?.id) throw new Error('Not tracked');
      return untrackAnime(trackedStatus.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tracked-status'] });
      queryClient.invalidateQueries({ queryKey: ['tracked'] });
    },
  });

  const handleDownload = useCallback(
    (episode: Episode) => {
      if (!anime) return;
      withFolder(async (folder) => {
        await startDownloads({
          anime_id: anime.id,
          anime_title: anime.title,
          anime_slug: anime.slug,
          cover_url: anime.cover_url,
          genres: anime.genres,
          plot: anime.plot,
          year: anime.year,
          source_site: site,
          dest_folder_override: folder || undefined,
          episodes: [{ episode_id: episode.id, episode_number: episode.number, episode_title: episode.title }],
        });
        queryClient.invalidateQueries({ queryKey: ['episodes'] });
      });
    },
    [anime, site, queryClient, withFolder],
  );

  const handleDownloadAll = useCallback(() => {
    if (!anime || !episodesData) return;
    const downloadable = episodesData.episodes.filter(
      (ep) => !ep.download_status || ep.download_status === 'failed',
    );
    if (downloadable.length === 0) return;

    withFolder(async (folder) => {
      await startDownloads({
        anime_id: anime.id,
        anime_title: anime.title,
        anime_slug: anime.slug,
        cover_url: anime.cover_url,
        genres: anime.genres,
        plot: anime.plot,
        year: anime.year,
        source_site: site,
        dest_folder_override: folder || undefined,
        episodes: downloadable.map((ep) => ({
          episode_id: ep.id,
          episode_number: ep.number,
          episode_title: ep.title,
        })),
      });
      queryClient.invalidateQueries({ queryKey: ['episodes'] });
    });
  }, [anime, episodesData, site, queryClient, withFolder]);

  const handleDownloadRange = useCallback(
    async (from: number, to: number) => {
      if (!anime) return;
      // Fetch episodes in the requested range from the API
      const rangeData = await getEpisodes(animeId, slug, from, to, site);
      const downloadable = rangeData.episodes.filter(
        (ep) => !ep.download_status || ep.download_status === 'failed',
      );
      if (downloadable.length === 0) return;

      withFolder(async (folder) => {
        await startDownloads({
          anime_id: anime.id,
          anime_title: anime.title,
          anime_slug: anime.slug,
          cover_url: anime.cover_url,
          genres: anime.genres,
          plot: anime.plot,
          year: anime.year,
          source_site: site,
          dest_folder_override: folder || undefined,
          episodes: downloadable.map((ep) => ({
            episode_id: ep.id,
            episode_number: ep.number,
            episode_title: ep.title,
          })),
        });
        queryClient.invalidateQueries({ queryKey: ['episodes'] });
      });
    },
    [anime, animeId, slug, site, queryClient, withFolder],
  );

  const handleDownloadSelected = useCallback(
    (selected: Episode[]) => {
      if (!anime || selected.length === 0) return;
      withFolder(async (folder) => {
        await startDownloads({
          anime_id: anime.id,
          anime_title: anime.title,
          anime_slug: anime.slug,
          cover_url: anime.cover_url,
          genres: anime.genres,
          plot: anime.plot,
          year: anime.year,
          source_site: site,
          dest_folder_override: folder || undefined,
          episodes: selected.map((ep) => ({
            episode_id: ep.id,
            episode_number: ep.number,
            episode_title: ep.title,
          })),
        });
        queryClient.invalidateQueries({ queryKey: ['episodes'] });
      });
    },
    [anime, site, queryClient, withFolder],
  );

  const handleWatch = useCallback(
    async (episode: Episode) => {
      if (!anime) return;
      try {
        setCurrentEpisode(episode);
        const data = await getStreamSource(episode.id, site);
        setStreamInfo({
          url: data.url,
          type: data.type,
          title: `${anime.title} — Ep. ${episode.number}`,
        });
      } catch (err) {
        setCurrentEpisode(null);
        alert(`Errore streaming: ${(err as Error).message}`);
      }
    },
    [anime, site],
  );

  // The player holds a signed CDN link that expires after ~24h; re-resolving the same
  // episode hands it a live one instead of leaving it stuck on a dead URL.
  const handleRefreshUrl = useCallback(async () => {
    if (!currentEpisode) return null;
    const data = await getStreamSource(currentEpisode.id, site);
    return data.url;
  }, [currentEpisode, site]);

  const nextEpisode = useMemo(() => {
    if (!currentEpisode || !episodesData?.episodes) return null;
    const currentNum = parseFloat(currentEpisode.number);
    return episodesData.episodes.find((ep) => parseFloat(ep.number) > currentNum) || null;
  }, [currentEpisode, episodesData]);

  const handleNext = useCallback(() => {
    if (nextEpisode) handleWatch(nextEpisode);
  }, [nextEpisode, handleWatch]);

  const handleLoadMore = useCallback(() => {
    setEpisodeEnd((prev) => prev + 120);
  }, []);

  if (animeLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="inline-block w-8 h-8 border-3 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  if (!anime) {
    return <div className="text-center py-20 text-error">Anime non trovato</div>;
  }

  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="relative rounded-2xl overflow-hidden bg-bg-secondary">
        {anime.banner_url && (
          <div className="absolute inset-0">
            <img
              src={anime.banner_url}
              alt=""
              className="w-full h-full object-cover opacity-30 blur-sm"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-bg-secondary via-bg-secondary/80 to-transparent" />
          </div>
        )}
        <div className="relative flex gap-6 p-6">
          {anime.cover_url && (
            <img
              src={anime.cover_url}
              alt={anime.title}
              className="w-40 h-56 object-cover rounded-xl shadow-lg flex-shrink-0"
            />
          )}
          <div className="flex-1 min-w-0 space-y-3">
            <div className="flex items-start gap-2 flex-wrap">
              <h1 className="text-2xl font-bold">{anime.title}</h1>
              {anime.dub && (
                <span className="px-2 py-0.5 bg-warning/90 text-black text-xs font-bold rounded mt-1">
                  ITA
                </span>
              )}
              <button
                onClick={() => trackedStatus?.tracked ? untrackMutation.mutate() : trackMutation.mutate()}
                disabled={trackMutation.isPending || untrackMutation.isPending}
                className={`ml-auto px-3 py-1.5 text-xs font-medium rounded-[5px] transition-colors flex items-center gap-1.5 ${
                  trackedStatus?.tracked
                    ? 'bg-accent text-white hover:bg-error'
                    : 'bg-accent/10 text-accent hover:bg-accent hover:text-white'
                }`}
              >
                <svg className="w-3.5 h-3.5" fill={trackedStatus?.tracked ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                </svg>
                {trackedStatus?.tracked ? 'Non seguire' : 'Segui'}
              </button>
            </div>
            {anime.title_eng && anime.title_eng !== anime.title && (
              <p className="text-sm text-text-secondary">{anime.title_eng}</p>
            )}
            <div className="flex flex-wrap gap-2">
              {anime.type && (
                <span className="px-2 py-0.5 bg-accent/20 text-accent text-xs rounded font-medium">
                  {anime.type}
                </span>
              )}
              {anime.year && (
                <span className="px-2 py-0.5 bg-bg-card text-text-secondary text-xs rounded">
                  {anime.year}
                </span>
              )}
              {anime.status && (
                <span className="px-2 py-0.5 bg-bg-card text-text-secondary text-xs rounded">
                  {anime.status}
                </span>
              )}
              {anime.episodes_count != null && (
                <span className="px-2 py-0.5 bg-bg-card text-text-secondary text-xs rounded">
                  {anime.episodes_count} episodi
                </span>
              )}
            </div>
            {anime.genres.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {anime.genres.map((genre) => (
                  <span
                    key={genre}
                    className="px-2 py-0.5 bg-bg-card border border-border text-text-secondary text-xs rounded-full"
                  >
                    {genre}
                  </span>
                ))}
              </div>
            )}
            {anime.plot && (
              <p className="text-sm text-text-secondary leading-relaxed line-clamp-4">
                {anime.plot}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Episodes */}
      {episodesLoading ? (
        <div className="flex items-center justify-center py-10">
          <span className="inline-block w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        </div>
      ) : episodesData ? (
        <EpisodeList
          episodes={episodesData.episodes}
          total={episodesData.total}
          hasMore={episodesData.has_more}
          onLoadMore={handleLoadMore}
          onDownload={handleDownload}
          onWatch={handleWatch}
          onDownloadAll={handleDownloadAll}
          onDownloadRange={handleDownloadRange}
          onDownloadSelected={handleDownloadSelected}
          onSchedule={() => setShowScheduleForm(true)}
          isLoadingMore={episodesFetching}
        />
      ) : null}

      {/* Video Player Overlay */}
      {streamInfo && (
        <VideoPlayer
          key={streamInfo.url}
          url={streamInfo.url}
          type={streamInfo.type}
          title={streamInfo.title}
          onClose={() => { setStreamInfo(null); setCurrentEpisode(null); }}
          onRefreshUrl={handleRefreshUrl}
          onNext={nextEpisode ? handleNext : undefined}
          nextEpisodeLabel={
            nextEpisode
              ? `Ep. ${nextEpisode.number}${nextEpisode.title ? ` — ${nextEpisode.title}` : ''}`
              : undefined
          }
        />
      )}

      {/* Destination folder browser — shown when a download is triggered */}
      {showFolderBrowser && (
        <FolderBrowser
          initialPath=""
          onSelect={(path) => {
            setShowFolderBrowser(false);
            pendingDownload?.(path);
            setPendingDownload(null);
          }}
          onClose={() => {
            setShowFolderBrowser(false);
            setPendingDownload(null);
          }}
        />
      )}

      {/* Schedule download form (anime + site preselected) */}
      {showScheduleForm && (
        <ScheduleForm
          presetAnime={{
            anime: {
              id: anime.id,
              slug: anime.slug,
              title: anime.title,
              title_eng: anime.title_eng,
              cover_url: anime.cover_url,
              type: anime.type,
              year: anime.year,
              episodes_count: anime.episodes_count,
              genres: anime.genres,
              dub: anime.dub,
              source_site: site,
            } satisfies AnimeSearchResult,
            site,
          }}
          onSubmit={async (req) => {
            await createSchedule(req);
            queryClient.invalidateQueries({ queryKey: ['scheduled'] });
            setShowScheduleForm(false);
          }}
          onCancel={() => setShowScheduleForm(false)}
        />
      )}
    </div>
  );
}
