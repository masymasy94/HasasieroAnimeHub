import { useEffect, useState } from 'react';
import { browseFolder, createFolder } from '../api/filesystem';
import type { BrowseResponse } from '../types/filesystem';

interface Props {
  initialPath?: string;
  onSelect: (path: string) => void;
  onClose: () => void;
}

export function FolderBrowser({ initialPath = '', onSelect, onClose }: Props) {
  const [current, setCurrent] = useState<BrowseResponse | null>(null);
  const [path, setPath] = useState(initialPath);
  const [error, setError] = useState<string | null>(null);
  const [newFolderName, setNewFolderName] = useState('');
  const [showNewFolder, setShowNewFolder] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    browseFolder(path)
      .then((data) => {
        if (!cancelled) setCurrent(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    try {
      const data = await createFolder(path, newFolderName.trim());
      setCurrent(data);
      setNewFolderName('');
      setShowNewFolder(false);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const folders = (current?.entries ?? []).filter((e) => e.is_dir);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-[520px] max-h-[80vh] flex flex-col bg-bg-secondary border border-border rounded-[5px] shadow-xl">
        <header className="p-4 border-b border-border flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-white">Seleziona cartella</h3>
          <button
            onClick={onClose}
            className="text-text-secondary hover:text-text-white text-lg leading-none"
            aria-label="Chiudi"
          >
            ×
          </button>
        </header>

        <div className="px-4 py-2 text-[11px] text-text-secondary border-b border-border">
          /downloads/{current?.current_path || ''}
        </div>

        {error && (
          <div className="px-4 py-2 text-xs text-error bg-error/10 border-b border-border">
            {error}
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-2">
          {current?.parent_path !== null && current !== null && (
            <button
              onClick={() => setPath(current.parent_path ?? '')}
              className="w-full text-left px-3 py-2 text-[13px] text-text-secondary hover:bg-bg-hover rounded"
            >
              .. (cartella superiore)
            </button>
          )}
          {folders.length === 0 && (
            <div className="px-3 py-4 text-center text-text-secondary text-xs">
              Nessuna sottocartella.
            </div>
          )}
          {folders.map((entry) => (
            <button
              key={entry.path}
              onClick={() => setPath(entry.path)}
              className="w-full text-left px-3 py-2 text-[13px] text-text-white hover:bg-bg-hover rounded flex items-center gap-2"
            >
              <svg
                className="w-4 h-4 text-accent"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"
                />
              </svg>
              {entry.name}
            </button>
          ))}
        </div>

        {showNewFolder ? (
          <div className="p-3 border-t border-border flex items-center gap-2">
            <input
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="nome cartella"
              className="flex-1 px-2 py-1 text-xs bg-bg-card border border-border rounded text-text-white"
            />
            <button
              onClick={handleCreateFolder}
              className="px-3 py-1 text-xs bg-accent text-white rounded"
            >
              Crea
            </button>
            <button
              onClick={() => {
                setShowNewFolder(false);
                setNewFolderName('');
              }}
              className="px-3 py-1 text-xs text-text-secondary"
            >
              Annulla
            </button>
          </div>
        ) : (
          <div className="p-3 border-t border-border flex items-center justify-between">
            <button
              onClick={() => setShowNewFolder(true)}
              className="px-3 py-1.5 text-xs text-text-secondary hover:text-text-white"
            >
              + Nuova cartella
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={onClose}
                className="px-3 py-1.5 text-xs text-text-secondary hover:text-text-white"
              >
                Annulla
              </button>
              <button
                onClick={() => onSelect(current?.current_path ?? '')}
                className="px-3 py-1.5 text-xs bg-accent text-white rounded"
              >
                Seleziona questa cartella
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
