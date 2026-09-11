import { useEffect, useRef, useState, useCallback } from 'react';
import Hls from 'hls.js';

interface VideoPlayerProps {
  url: string;
  type: 'mp4' | 'm3u8';
  onClose: () => void;
  title?: string;
  onNext?: () => void;
  nextEpisodeLabel?: string;
  /** Re-resolve the episode to a fresh URL, or null if it can't be resolved. */
  onRefreshUrl?: () => Promise<string | null>;
}

const COUNTDOWN_SECONDS = 5;

export function VideoPlayer({ url, type, onClose, title, onNext, nextEpisodeLabel, onRefreshUrl }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCountdown, setShowCountdown] = useState(false);
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // What we actually load: the prop at first, then whatever a refresh resolved to.
  // The parent keys us on `url`, so a new episode remounts and resets all of this.
  const [srcUrl, setSrcUrl] = useState(url);
  const resumeAtRef = useRef(0);
  const recoveredRef = useRef(false);
  // Held in a ref so the setup effect doesn't depend on the parent's callback
  // identity — an inline arrow up there would reload the video on every render.
  const refreshRef = useRef(onRefreshUrl);
  useEffect(() => {
    refreshRef.current = onRefreshUrl;
  }, [onRefreshUrl]);

  const clearCountdown = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setShowCountdown(false);
    setCountdown(COUNTDOWN_SECONDS);
  }, []);

  const handlePlayNow = useCallback(() => {
    clearCountdown();
    onNext?.();
  }, [clearCountdown, onNext]);

  const handleCancel = useCallback(() => {
    clearCountdown();
  }, [clearCountdown]);

  // Stream setup
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // Reset countdown state on new URL
    clearCountdown();
    setError(null);

    const startPlayback = () => {
      if (resumeAtRef.current > 0) video.currentTime = resumeAtRef.current;
      video.play().catch(() => {});
    };

    // The CDN link is signed and dies after ~24h — on a tab left open overnight every
    // retry then gets a 410 and the picture just freezes. Re-resolve the episode once
    // and resume where we were; failing again without playing in between is a real error.
    const recover = async (message: string) => {
      if (!refreshRef.current || recoveredRef.current) {
        setError(message);
        return;
      }
      recoveredRef.current = true;
      resumeAtRef.current = video.currentTime || resumeAtRef.current;
      const fresh = await refreshRef.current().catch(() => null);
      if (fresh) setSrcUrl(fresh);
      else setError(message);
    };

    const handleMediaError = () => recover('Errore streaming: sorgente non più disponibile');
    const clearRecovery = () => {
      recoveredRef.current = false;
    };

    video.addEventListener('loadedmetadata', startPlayback);
    video.addEventListener('error', handleMediaError);
    video.addEventListener('playing', clearRecovery);

    if (type === 'm3u8') {
      if (Hls.isSupported()) {
        const hls = new Hls({
          maxBufferLength: 60,
          maxMaxBufferLength: 120,
        });
        hlsRef.current = hls;
        hls.loadSource(srcUrl);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, startPlayback);
        hls.on(Hls.Events.ERROR, (_event, data) => {
          if (data.fatal) {
            recover(`Errore streaming: ${data.details}`);
          }
        });
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = srcUrl;
      } else {
        setError('Il browser non supporta lo streaming HLS');
      }
    } else {
      video.src = srcUrl;
    }

    return () => {
      video.removeEventListener('loadedmetadata', startPlayback);
      video.removeEventListener('error', handleMediaError);
      video.removeEventListener('playing', clearRecovery);
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [srcUrl, type, clearCountdown]);

  // Video ended — start countdown if next episode available
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleEnded = () => {
      if (!onNext) return;
      setShowCountdown(true);
      setCountdown(COUNTDOWN_SECONDS);
    };

    video.addEventListener('ended', handleEnded);
    return () => video.removeEventListener('ended', handleEnded);
  }, [onNext]);

  // Countdown timer
  useEffect(() => {
    if (!showCountdown) return;

    intervalRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearCountdown();
          onNext?.();
          return COUNTDOWN_SECONDS;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [showCountdown, onNext, clearCountdown]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        clearCountdown();
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose, clearCountdown]);

  return (
    <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center" onClick={onClose}>
      <div
        className="relative w-full max-w-5xl mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          {title && (
            <span className="text-white text-sm font-medium truncate mr-4">{title}</span>
          )}
          <button
            onClick={onClose}
            className="text-white/70 hover:text-white transition-colors ml-auto"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error ? (
          <div className="bg-bg-secondary rounded-lg p-8 text-center text-error">
            {error}
          </div>
        ) : (
          <div className="relative">
            <video
              ref={videoRef}
              controls
              autoPlay
              className="w-full rounded-lg bg-black"
              style={{ maxHeight: '80vh' }}
            />

            {/* Countdown overlay */}
            {showCountdown && (
              <div className="absolute inset-0 bg-black/80 rounded-lg flex flex-col items-center justify-center gap-4">
                <p className="text-white/70 text-sm">Prossimo episodio tra</p>
                <span className="text-white text-5xl font-bold tabular-nums">{countdown}</span>
                {nextEpisodeLabel && (
                  <p className="text-white/90 text-base font-medium">{nextEpisodeLabel}</p>
                )}
                <div className="flex gap-3 mt-2">
                  <button
                    onClick={handlePlayNow}
                    className="px-5 py-2 bg-accent text-white text-sm font-medium rounded-[5px] hover:bg-accent-hover transition-colors"
                  >
                    Riproduci ora
                  </button>
                  <button
                    onClick={handleCancel}
                    className="px-5 py-2 bg-white/10 text-white text-sm rounded-[5px] hover:bg-white/20 transition-colors"
                  >
                    Annulla
                  </button>
                </div>
                {/* Progress bar */}
                <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/10 rounded-b-lg overflow-hidden">
                  <div
                    className="h-full bg-accent transition-all duration-1000 ease-linear"
                    style={{ width: `${(countdown / COUNTDOWN_SECONDS) * 100}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
