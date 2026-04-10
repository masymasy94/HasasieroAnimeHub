import { useEffect, useRef, useState } from 'react';
import { getHighestEpisode } from '../api/filesystem';
import { streamSearch } from '../api/search';
import { getSites } from '../api/sites';
import type { AnimeSearchResult } from '../types/anime';
import type {
  PatternType,
  ScheduleCreateRequest,
  ScheduledDownload,
} from '../types/scheduled';
import { PATTERN_PRESETS } from '../types/scheduled';
import { FolderBrowser } from './FolderBrowser';

interface Props {
  initial?: ScheduledDownload | null;
  onSubmit: (req: ScheduleCreateRequest) => Promise<void>;
  onCancel: () => void;
}

export function ScheduleForm({ initial, onSubmit, onCancel }: Props) {
  const [sites, setSites] = useState<{ id: string; name: string }[]>([]);
  const [siteId, setSiteId] = useState(initial?.source_site ?? '');
  const [animeQuery, setAnimeQuery] = useState(initial?.anime_title ?? '');
  const [searchResults, setSearchResults] = useState<AnimeSearchResult[]>([]);
  const [selectedAnime, setSelectedAnime] = useState<AnimeSearchResult | null>(
    initial
      ? ({
          id: initial.anime_id,
          slug: initial.anime_slug,
          title: initial.anime_title,
          title_eng: null,
          cover_url: initial.cover_url,
          type: null,
          year: null,
          episodes_count: null,
          genres: [],
          dub: false,
          source_site: initial.source_site,
        } satisfies AnimeSearchResult)
      : null,
  );
  const abortSearchRef = useRef<(() => void) | null>(null);

  const [destFolder, setDestFolder] = useState(initial?.dest_folder ?? '');
  const [showBrowser, setShowBrowser] = useState(false);
  const [lastEpisode, setLastEpisode] = useState<number | null>(null);
  const [titleMatch, setTitleMatch] = useState<boolean | null>(null);

  // Pattern state
  const [patternKind, setPatternKind] = useState<'preset' | 'custom'>(
    initial?.filename_template_type ?? 'preset',
  );
  const [presetId, setPresetId] = useState(() => {
    if (initial?.filename_template_type === 'preset') {
      const found = PATTERN_PRESETS.find((p) => p.template === initial.filename_template);
      return found?.id ?? PATTERN_PRESETS[0].id;
    }
    return PATTERN_PRESETS[0].id;
  });
  const [customTemplate, setCustomTemplate] = useState(
    initial?.filename_template_type === 'custom' ? initial.filename_template : '',
  );

  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [submitting, setSubmitting] = useState(false);

  // Scan folder for highest existing episode when destFolder or anime changes
  useEffect(() => {
    if (!destFolder) {
      setLastEpisode(null);
      setTitleMatch(null);
      return;
    }
    let cancelled = false;
    getHighestEpisode(destFolder, selectedAnime?.title ?? '')
      .then((data) => {
        if (!cancelled) {
          setLastEpisode(data.highest_episode);
          setTitleMatch(data.title_match);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLastEpisode(null);
          setTitleMatch(null);
        }
      });
    return () => { cancelled = true; };
  }, [destFolder, selectedAnime?.title]);

  // Load provider list
  useEffect(() => {
    getSites().then((data) => {
      setSites(data.sites);
      if (!siteId && data.sites.length > 0) {
        setSiteId(data.sites[0].id);
      }
    });
  }, []);

  // Search debounce — streams results and keeps only the selected site.
  useEffect(() => {
    if (!animeQuery || animeQuery === selectedAnime?.title || !siteId) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(() => {
      // Cancel any previous in-flight stream
      abortSearchRef.current?.();
      setSearchResults([]);
      const abort = streamSearch(
        animeQuery,
        (site, results) => {
          if (site === siteId) {
            setSearchResults((prev) => [...prev, ...results].slice(0, 8));
          }
        },
        () => {
          abortSearchRef.current = null;
        },
        () => {
          abortSearchRef.current = null;
        },
      );
      abortSearchRef.current = abort;
    }, 300);
    return () => {
      clearTimeout(timer);
      abortSearchRef.current?.();
      abortSearchRef.current = null;
    };
  }, [animeQuery, siteId, selectedAnime?.title]);

  const handleSubmit = async () => {
    if (!selectedAnime || !siteId || !destFolder) return;
    setSubmitting(true);
    try {
      const template =
        patternKind === 'preset'
          ? PATTERN_PRESETS.find((p) => p.id === presetId)!.template
          : customTemplate;
      const patternType: PatternType = patternKind;
      await onSubmit({
        anime_id: selectedAnime.id,
        anime_slug: selectedAnime.slug,
        anime_title: selectedAnime.title,
        cover_url: selectedAnime.cover_url ?? null,
        source_site: siteId,
        dest_folder: destFolder,
        filename_template: template,
        filename_template_type: patternType,
        enabled,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit =
    !!selectedAnime &&
    !!siteId &&
    !!destFolder &&
    (patternKind === 'preset' || customTemplate.trim().length > 0);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60">
      <div className="w-[560px] max-h-[90vh] overflow-y-auto bg-bg-secondary border border-border rounded-[5px] shadow-xl">
        <header className="p-4 border-b border-border flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-white">
            {initial ? 'Modifica download programmato' : 'Nuovo download programmato'}
          </h3>
          <button
            onClick={onCancel}
            className="text-text-secondary hover:text-text-white text-lg leading-none"
          >
            ×
          </button>
        </header>

        <div className="p-4 space-y-4">
          {/* Site */}
          <div>
            <label className="block text-[11px] text-text-secondary mb-1">Sito</label>
            <select
              value={siteId}
              onChange={(e) => setSiteId(e.target.value)}
              className="w-full px-2 py-1.5 text-xs bg-bg-card border border-border rounded text-text-white"
            >
              {sites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          {/* Anime search */}
          <div>
            <label className="block text-[11px] text-text-secondary mb-1">Anime</label>
            <input
              value={animeQuery}
              onChange={(e) => {
                setAnimeQuery(e.target.value);
                setSelectedAnime(null);
              }}
              placeholder="Cerca titolo..."
              className="w-full px-2 py-1.5 text-xs bg-bg-card border border-border rounded text-text-white"
            />
            {!selectedAnime && searchResults.length > 0 && (
              <div className="mt-1 border border-border rounded bg-bg-card max-h-40 overflow-y-auto">
                {searchResults.map((r) => (
                  <button
                    key={`${r.id}-${r.slug}`}
                    onClick={() => {
                      setSelectedAnime(r);
                      setAnimeQuery(r.title);
                      setSearchResults([]);
                    }}
                    className="w-full text-left px-2 py-1.5 text-xs text-text-white hover:bg-bg-hover"
                  >
                    {r.title}
                  </button>
                ))}
              </div>
            )}
            {selectedAnime && (
              <div className="mt-1 text-[11px] text-accent">
                Selezionato: {selectedAnime.title}
              </div>
            )}
          </div>

          {/* Destination folder */}
          <div>
            <label className="block text-[11px] text-text-secondary mb-1">
              Cartella di destinazione (dentro /downloads)
            </label>
            <div className="flex items-center gap-2">
              <input
                value={destFolder}
                readOnly
                placeholder="(non selezionata)"
                className="flex-1 px-2 py-1.5 text-xs bg-bg-card border border-border rounded text-text-white"
              />
              <button
                onClick={() => setShowBrowser(true)}
                className="px-3 py-1.5 text-xs bg-accent/15 text-accent rounded border border-accent/30"
              >
                Sfoglia...
              </button>
            </div>
            {destFolder && lastEpisode !== null && (
              <div className="mt-1 space-y-1">
                <div className="text-[11px] text-text-secondary">
                  {lastEpisode > 0
                    ? <>Ultimo episodio trovato: <span className="text-accent font-medium">{lastEpisode}</span> — il prossimo download partira dall'episodio {lastEpisode + 1}</>
                    : <>Nessun episodio trovato nella cartella — il download partira dall'episodio 1</>
                  }
                </div>
                {selectedAnime && titleMatch === false && lastEpisode > 0 && (
                  <div className="text-[11px] text-warning bg-warning/10 px-2 py-1 rounded border border-warning/30">
                    Attenzione: nessun file nella cartella contiene "{selectedAnime.title}" nel nome. Potrebbe non essere la cartella giusta per questa serie.
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Pattern selector */}
          <div>
            <label className="block text-[11px] text-text-secondary mb-1">
              Pattern nome file
            </label>
            <select
              value={patternKind === 'custom' ? '__custom__' : presetId}
              onChange={(e) => {
                if (e.target.value === '__custom__') {
                  setPatternKind('custom');
                } else {
                  setPatternKind('preset');
                  setPresetId(e.target.value);
                }
              }}
              className="w-full px-2 py-1.5 text-xs bg-bg-card border border-border rounded text-text-white"
            >
              {PATTERN_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
              <option value="__custom__">Custom (scrivi nome, XX = episodio)</option>
            </select>
            {patternKind === 'custom' && (
              <div className="mt-2 space-y-1">
                <input
                  value={customTemplate}
                  onChange={(e) => setCustomTemplate(e.target.value)}
                  placeholder="es. Mio File"
                  className="w-full px-2 py-1.5 text-xs bg-bg-card border border-border rounded text-text-white"
                />
                <div className="text-[11px] text-text-secondary">
                  Anteprima: {customTemplate ? `${customTemplate} 06.mp4` : '—'}
                </div>
              </div>
            )}
          </div>

          {/* Enabled */}
          <label className="flex items-center gap-2 text-xs text-text-white">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            Attivo
          </label>
        </div>

        <div className="p-4 border-t border-border flex items-center justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-xs text-text-secondary hover:text-text-white"
          >
            Annulla
          </button>
          <button
            disabled={!canSubmit || submitting}
            onClick={handleSubmit}
            className="px-4 py-1.5 text-xs bg-accent text-white rounded disabled:opacity-50"
          >
            {submitting ? 'Salvataggio...' : 'Salva'}
          </button>
        </div>
      </div>

      {showBrowser && (
        <FolderBrowser
          initialPath={destFolder}
          onSelect={(path) => {
            setDestFolder(path);
            setShowBrowser(false);
          }}
          onClose={() => setShowBrowser(false)}
        />
      )}
    </div>
  );
}
