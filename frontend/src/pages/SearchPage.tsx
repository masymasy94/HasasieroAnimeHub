import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { streamSearch, getLatestAnime } from '../api/search';
import { SearchBar } from '../components/SearchBar';
import { AnimeCard } from '../components/AnimeCard';
import type { AnimeSearchResult } from '../types/anime';

const TYPE_FILTERS = ['Tutti', 'TV', 'Movie', 'OVA', 'ONA', 'Special'] as const;
const DUB_FILTERS = ['Tutti', 'SUB', 'ITA'] as const;

const TYPE_ORDER: Record<string, number> = { TV: 0, Movie: 1, ONA: 2, OVA: 3, Special: 4 };

export function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<AnimeSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [siteFilter, setSiteFilter] = useState<string>('Tutti');
  const [typeFilter, setTypeFilter] = useState<string>('Tutti');
  const [dubFilter, setDubFilter] = useState<string>('Tutti');
  const abortRef = useRef<(() => void) | null>(null);

  const handleSearch = useCallback((q: string) => setQuery(q), []);

  // Stream search: cancel previous, start new
  useEffect(() => {
    // Cancel any in-flight stream
    abortRef.current?.();
    abortRef.current = null;

    if (query.length < 2) {
      setResults([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    setResults([]);
    setIsLoading(true);
    setError(null);

    const abort = streamSearch(
      query,
      (_site, newResults) => {
        setResults((prev) => [...prev, ...newResults]);
      },
      () => {
        setIsLoading(false);
      },
      (err) => {
        setError(err);
        setIsLoading(false);
      },
    );

    abortRef.current = abort;

    return () => {
      abort();
    };
  }, [query]);

  const { data: latestData } = useQuery({
    queryKey: ['latest'],
    queryFn: getLatestAnime,
    staleTime: 5 * 60 * 1000,
  });

  const filtered = useMemo(() => {
    if (!results.length) return [];

    let list = [...results];

    if (siteFilter !== 'Tutti') {
      list = list.filter((a) => a.source_site === siteFilter);
    }

    if (typeFilter !== 'Tutti') {
      list = list.filter((a) => a.type === typeFilter);
    }

    if (dubFilter === 'SUB') {
      list = list.filter((a) => !a.dub);
    } else if (dubFilter === 'ITA') {
      list = list.filter((a) => a.dub);
    }

    list.sort((a, b) => {
      const typeA = TYPE_ORDER[a.type ?? ''] ?? 99;
      const typeB = TYPE_ORDER[b.type ?? ''] ?? 99;
      if (typeA !== typeB) return typeA - typeB;
      return (b.year ?? '').localeCompare(a.year ?? '');
    });

    return list;
  }, [results, siteFilter, typeFilter, dubFilter]);

  const siteCounts = useMemo(() => {
    if (!results.length) return {};
    const counts: Record<string, number> = {};
    for (const r of results) {
      const s = r.source_site ?? 'animeunity';
      counts[s] = (counts[s] || 0) + 1;
    }
    return counts;
  }, [results]);

  const typeCounts = useMemo(() => {
    if (!results.length) return {};
    const counts: Record<string, number> = {};
    for (const r of results) {
      const t = r.type ?? 'Altro';
      counts[t] = (counts[t] || 0) + 1;
    }
    return counts;
  }, [results]);

  const hasResults = query.length >= 2 && results.length > 0;
  const showHero = !hasResults && !isLoading && !error;

  return (
    <div className="space-y-6">
      {/* Hero section with gradient background */}
      <div
        className="relative -m-6 mb-0 overflow-hidden transition-all duration-700"
        style={{ height: showHero ? '280px' : '140px' }}
      >
        <div
          className="absolute inset-0 transition-all duration-700"
          style={{
            background: showHero
              ? `
                radial-gradient(ellipse 80% 50% at 70% 20%, rgba(61,180,242,0.15) 0%, transparent 60%),
                radial-gradient(ellipse 60% 40% at 20% 60%, rgba(99,102,241,0.12) 0%, transparent 50%),
                radial-gradient(ellipse 40% 30% at 85% 70%, rgba(168,85,247,0.10) 0%, transparent 50%),
                linear-gradient(to bottom, #0d1b2a 0%, #0b1622 100%)
              `
              : 'linear-gradient(to bottom, #0d1b2a 0%, #0b1622 100%)',
          }}
        />
        {showHero && (
          <>
            <div className="absolute inset-0 opacity-[0.03]" style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%233db4f2' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
            }} />
            <div className="absolute top-[15%] left-[10%] w-1 h-1 rounded-full bg-accent/30 animate-pulse" />
            <div className="absolute top-[25%] right-[20%] w-0.5 h-0.5 rounded-full bg-white/20 animate-pulse" style={{ animationDelay: '1s' }} />
            <div className="absolute top-[40%] left-[60%] w-0.5 h-0.5 rounded-full bg-accent/20 animate-pulse" style={{ animationDelay: '2s' }} />
            <div className="absolute top-[10%] right-[35%] w-1 h-1 rounded-full bg-purple-400/20 animate-pulse" style={{ animationDelay: '0.5s' }} />
            <div className="absolute top-[35%] left-[30%] w-0.5 h-0.5 rounded-full bg-white/15 animate-pulse" style={{ animationDelay: '1.5s' }} />
          </>
        )}
        <div className="relative z-10 flex flex-col items-center justify-center h-full px-6">
          <div className="text-center space-y-2 mb-5">
            <h1
              className={`font-bold text-white drop-shadow-lg transition-all duration-500 ${showHero ? 'text-3xl' : 'text-lg'}`}
            >
              Cerca un anime
            </h1>
            {showHero && (
              <p className="text-gray-300 text-sm drop-shadow">
                Cerca, guarda e scarica da AnimeUnity, AnimeWorld e AnimeSaturn
              </p>
            )}
          </div>
          <div className={`w-full transition-all duration-500 ${showHero ? 'max-w-xl' : 'max-w-2xl'}`}>
            <SearchBar onSearch={handleSearch} isLoading={isLoading} />
          </div>
        </div>
      </div>

      {error && (
        <div className="text-center py-8 text-error text-sm">
          Errore nella ricerca: {error.message}
        </div>
      )}

      {/* Filters */}
      {hasResults && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-4">
            {/* Site filter */}
            <div className="flex gap-1">
              <button
                onClick={() => setSiteFilter('Tutti')}
                className={`px-3 py-1.5 text-xs font-medium rounded-[5px] transition-colors ${
                  siteFilter === 'Tutti'
                    ? 'bg-accent text-white'
                    : 'bg-bg-secondary text-text-secondary hover:text-text-white border border-border'
                }`}
              >
                Tutti
              </button>
              {Object.entries(siteCounts).map(([site]) => (
                <button
                  key={site}
                  onClick={() => setSiteFilter(site)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-[5px] transition-colors ${
                    siteFilter === site
                      ? 'bg-accent text-white'
                      : 'bg-bg-secondary text-text-secondary hover:text-text-white border border-border'
                  }`}
                >
                  {site === 'animeunity' ? 'AnimeUnity' : site === 'animeworld' ? 'AnimeWorld' : site === 'animesaturn' ? 'AnimeSaturn' : site}
                </button>
              ))}
            </div>

            {/* Type filter */}
            <div className="flex gap-1">
              {TYPE_FILTERS.map((t) => {
                const count = t === 'Tutti' ? results.length : (typeCounts[t] || 0);
                if (t !== 'Tutti' && count === 0) return null;
                return (
                  <button
                    key={t}
                    onClick={() => setTypeFilter(t)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-[5px] transition-colors ${
                      typeFilter === t
                        ? 'bg-accent text-white'
                        : 'bg-bg-secondary text-text-secondary hover:text-text-white border border-border'
                    }`}
                  >
                    {t}
                  </button>
                );
              })}
            </div>

            {/* Dub filter */}
            <div className="flex gap-1">
              {DUB_FILTERS.map((d) => (
                <button
                  key={d}
                  onClick={() => setDubFilter(d)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-[5px] transition-colors ${
                    dubFilter === d
                      ? 'bg-accent text-white'
                      : 'bg-bg-secondary text-text-secondary hover:text-text-white border border-border'
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

        </div>
      )}

      {/* Results */}
      {filtered.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {filtered.map((anime) => (
            <AnimeCard key={`${anime.source_site}-${anime.id}`} anime={anime} site={anime.source_site} />
          ))}
        </div>
      )}

      {hasResults && filtered.length === 0 && (
        <div className="text-center py-12 text-text-secondary">
          Nessun risultato con i filtri selezionati
        </div>
      )}

      {query.length >= 2 && !isLoading && results.length === 0 && (
        <div className="text-center py-12 text-text-secondary">
          Nessun risultato per "{query}"
        </div>
      )}

      {/* Latest / In onda ora */}
      {showHero && latestData?.results && latestData.results.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-text-white mb-4">Ultime uscite</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {latestData.results.map((anime) => (
              <AnimeCard key={`${anime.source_site}-${anime.id}`} anime={anime} site={anime.source_site} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
