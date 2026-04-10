import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Sidebar } from './components/Layout/Sidebar';
import { Header } from './components/Layout/Header';
import { SearchPage } from './pages/SearchPage';
import { AnimeDetailPage } from './pages/AnimeDetailPage';
import { DownloadsPage } from './pages/DownloadsPage';
import { SettingsPage } from './pages/SettingsPage';
import { ScheduledPage } from './pages/ScheduledPage';
import { TrackedPage } from './pages/TrackedPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <Header />
            <main className="flex-1 overflow-y-auto p-6">
              <Routes>
                <Route path="/" element={<Navigate to="/search" replace />} />
                <Route path="/search" element={<SearchPage />} />
                <Route path="/anime/:animePath" element={<AnimeDetailPage />} />
                <Route path="/downloads" element={<DownloadsPage />} />
                <Route path="/tracked" element={<TrackedPage />} />
                <Route path="/scheduled" element={<ScheduledPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </main>
          </div>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
