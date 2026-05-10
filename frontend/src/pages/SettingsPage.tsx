import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, updateSettings, testTelegram, testJellyfin } from '../api/settings';

export function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  });

  const [maxConcurrent, setMaxConcurrent] = useState(2);
  const [telegramBotToken, setTelegramBotToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [jellyfinUrl, setJellyfinUrl] = useState('');
  const [jellyfinApiKey, setJellyfinApiKey] = useState('');
  const [jellyfinEnabled, setJellyfinEnabled] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; error?: string } | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [jfTestResult, setJfTestResult] = useState<{ success: boolean; message?: string; error?: string } | null>(null);
  const [jfTestLoading, setJfTestLoading] = useState(false);

  useEffect(() => {
    if (settings) {
      setMaxConcurrent(settings.max_concurrent_downloads);
      setTelegramBotToken(settings.telegram_bot_token || '');
      setTelegramChatId(settings.telegram_chat_id || '');
      setJellyfinUrl(settings.jellyfin_url || '');
      setJellyfinApiKey(settings.jellyfin_api_key || '');
      setJellyfinEnabled(!!settings.jellyfin_enabled);
    }
  }, [settings]);

  const mutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const handleSave = () => {
    mutation.mutate({
      max_concurrent_downloads: maxConcurrent,
      telegram_bot_token: telegramBotToken,
      telegram_chat_id: telegramChatId,
      jellyfin_url: jellyfinUrl,
      jellyfin_api_key: jellyfinApiKey,
      jellyfin_enabled: jellyfinEnabled,
    });
  };

  const handleTestTelegram = async () => {
    setTestLoading(true);
    setTestResult(null);
    try {
      const result = await testTelegram();
      setTestResult(result);
    } catch {
      setTestResult({ success: false, error: 'Errore di rete' });
    }
    setTestLoading(false);
    setTimeout(() => setTestResult(null), 4000);
  };

  const handleTestJellyfin = async () => {
    // Persist URL/key first so the backend tests against current input.
    await mutation.mutateAsync({
      jellyfin_url: jellyfinUrl,
      jellyfin_api_key: jellyfinApiKey,
    });
    setJfTestLoading(true);
    setJfTestResult(null);
    try {
      const result = await testJellyfin();
      setJfTestResult(result);
    } catch {
      setJfTestResult({ success: false, error: 'Errore di rete' });
    }
    setJfTestLoading(false);
    setTimeout(() => setJfTestResult(null), 5000);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="inline-block w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-2xl font-bold text-text-white">Impostazioni</h1>

      <div className="bg-bg-secondary border border-border rounded-[5px] p-6 space-y-5">
        {/* Download directory */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-text-white">
            Cartella di destinazione
          </label>
          <div className="flex items-center gap-3 px-4 py-3 bg-bg-primary border border-border rounded-[5px]">
            <svg className="w-5 h-5 text-accent flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <span className="text-sm text-text-white font-mono">
              {settings?.host_download_path || settings?.download_dir || '/downloads'}
            </span>
          </div>
          <p className="text-xs text-text-secondary leading-relaxed">
            Per cambiare la cartella, ferma il container e modifica <code className="px-1.5 py-0.5 bg-bg-hover rounded text-accent text-[11px]">DOWNLOAD_PATH</code> nel file <code className="px-1.5 py-0.5 bg-bg-hover rounded text-accent text-[11px]">.env</code> o avvia con:
          </p>
          <pre className="text-xs text-accent bg-bg-primary border border-border rounded-[5px] px-3 py-2 overflow-x-auto">
            DOWNLOAD_PATH=/percorso/desiderato docker-compose up -d
          </pre>
        </div>

        {/* Max concurrent */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-text-white">
            Download simultanei
          </label>
          <input
            type="number"
            min={1}
            max={5}
            value={maxConcurrent}
            onChange={(e) => setMaxConcurrent(parseInt(e.target.value) || 1)}
            className="w-32 px-4 py-2.5 bg-bg-primary border border-border rounded-[5px] text-text-white text-sm focus:outline-none focus:border-accent transition-colors"
          />
        </div>
      </div>

      {/* Telegram Notifications */}
      <div className="bg-bg-secondary border border-border rounded-[5px] p-6 space-y-5">
        <h2 className="text-lg font-semibold text-text-white">Notifiche Telegram</h2>
        <p className="text-xs text-text-secondary">
          Ricevi un riepilogo su Telegram al termine di ogni ciclo di download programmati.
        </p>

        <div className="space-y-2">
          <label className="block text-sm font-medium text-text-white">
            Bot Token
          </label>
          <input
            type="password"
            value={telegramBotToken}
            onChange={(e) => setTelegramBotToken(e.target.value)}
            placeholder="123456:ABC-DEF1234..."
            className="w-full px-4 py-2.5 bg-bg-primary border border-border rounded-[5px] text-text-white text-sm focus:outline-none focus:border-accent transition-colors placeholder:text-text-secondary/50"
          />
          <p className="text-[11px] text-text-secondary">
            Crea un bot con <span className="text-accent">@BotFather</span> su Telegram e copia il token.
          </p>
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium text-text-white">
            Chat ID
          </label>
          <input
            type="text"
            value={telegramChatId}
            onChange={(e) => setTelegramChatId(e.target.value)}
            placeholder="es. 123456789"
            className="w-full px-4 py-2.5 bg-bg-primary border border-border rounded-[5px] text-text-white text-sm focus:outline-none focus:border-accent transition-colors placeholder:text-text-secondary/50"
          />
          <p className="text-[11px] text-text-secondary">
            Invia un messaggio al bot, poi apri <span className="text-accent">https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</span> per trovare il tuo chat ID.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleTestTelegram}
            disabled={testLoading || !telegramBotToken || !telegramChatId}
            className="px-4 py-2 bg-bg-primary border border-border text-text-white text-sm rounded-[5px] hover:border-accent disabled:opacity-50 transition-colors"
          >
            {testLoading ? 'Invio...' : 'Invia test'}
          </button>
          {testResult && (
            <span className={`text-sm font-medium ${testResult.success ? 'text-success' : 'text-error'}`}>
              {testResult.success ? 'Messaggio inviato!' : testResult.error}
            </span>
          )}
        </div>
      </div>

      {/* Jellyfin */}
      <div className="bg-bg-secondary border border-border rounded-[5px] p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-text-white">Jellyfin</h2>
            <p className="text-xs text-text-secondary">
              Avvia automaticamente la scansione della libreria al termine di ogni download.
            </p>
          </div>
          <label className="inline-flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={jellyfinEnabled}
              onChange={(e) => setJellyfinEnabled(e.target.checked)}
              className="w-4 h-4 accent-accent"
            />
            <span className="text-xs text-text-white">Attivo</span>
          </label>
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium text-text-white">
            URL del server
          </label>
          <input
            type="text"
            value={jellyfinUrl}
            onChange={(e) => setJellyfinUrl(e.target.value)}
            placeholder="es. http://jellyfin:8096"
            className="w-full px-4 py-2.5 bg-bg-primary border border-border rounded-[5px] text-text-white text-sm focus:outline-none focus:border-accent transition-colors placeholder:text-text-secondary/50"
          />
          <p className="text-[11px] text-text-secondary">
            Indirizzo raggiungibile dal container Hasasiero (no trailing slash).
          </p>
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium text-text-white">
            API Key
          </label>
          <input
            type="password"
            value={jellyfinApiKey}
            onChange={(e) => setJellyfinApiKey(e.target.value)}
            placeholder="••••••••"
            className="w-full px-4 py-2.5 bg-bg-primary border border-border rounded-[5px] text-text-white text-sm focus:outline-none focus:border-accent transition-colors placeholder:text-text-secondary/50"
          />
          <p className="text-[11px] text-text-secondary">
            Genera una chiave in Jellyfin → <span className="text-accent">Dashboard → API Keys</span>.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleTestJellyfin}
            disabled={jfTestLoading || !jellyfinUrl || !jellyfinApiKey}
            className="px-4 py-2 bg-bg-primary border border-border text-text-white text-sm rounded-[5px] hover:border-accent disabled:opacity-50 transition-colors"
          >
            {jfTestLoading ? 'Test...' : 'Test connessione'}
          </button>
          {jfTestResult && (
            <span className={`text-sm font-medium ${jfTestResult.success ? 'text-success' : 'text-error'}`}>
              {jfTestResult.success ? jfTestResult.message || 'OK' : jfTestResult.error}
            </span>
          )}
        </div>
      </div>

      {/* Save */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          className="px-6 py-2.5 bg-accent text-white text-sm font-medium rounded-[5px] hover:bg-accent-hover disabled:opacity-50 transition-colors"
        >
          {mutation.isPending ? 'Salvataggio...' : 'Salva'}
        </button>
        {saved && (
          <span className="text-sm text-success font-medium">Salvato!</span>
        )}
      </div>
    </div>
  );
}
