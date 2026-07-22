import { useState, useMemo, useEffect } from 'react';
import { Button } from './components/ui/button';
import { Badge } from './components/ui/badge';
import { Moon, Sun, Settings, Monitor } from 'lucide-react';

import { ScrapingControls } from './components/ScrapingControls';
import { StatsCharts } from './components/StatsCharts';
import { GoogleSheetsIntegration } from './components/GoogleSheetsIntegration';
import { SocialMediaIntegration } from './components/SocialMediaIntegration';
import { PriceHistoryChart } from './components/PriceHistoryChart';
import { AdvancedSettings } from './components/AdvancedSettings';
import { GameflipIntegration } from './components/GameflipIntegration';
import { KofiIntegration } from './components/KofiIntegration';
import { XboxProductViewer } from './components/XboxProductViewer';
import { BulkUploadManager } from './components/BulkUploadManager';
import RegionalPriceExplorer from './components/RegionalPriceExplorer';
import { VariantExplorer } from './components/VariantExplorer';
import { GameCards } from './components/GameCards';
import { Sidebar, NAV_GROUPS, NavItem } from './components/Sidebar';
import { useScraper } from './hooks/useScraper';

export default function App() {
  const [darkMode, setDarkMode] = useState(true);
  const [sel, setSel] = useState<NavItem>(NAV_GROUPS[0].items[0]); // Game Comparison
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const [isElectron, setIsElectron] = useState(false);
  const [appVersion, setAppVersion] = useState('2.0.0');

  const {
    games, selectedGames, regionStats, priceHistory, progress,
    startScraping, pauseScraping, stopScraping,
  } = useScraper();

  useEffect(() => {
    if (window.electronAPI) {
      setIsElectron(true);
      window.electronAPI.getVersion?.().then((v: string) => setAppVersion(v)).catch(() => {});
    }
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
  }, [darkMode]);

  const selectedGameObjects = useMemo(
    () => games.filter((g) => selectedGames.has(g.id)), [games, selectedGames]);

  const onSelect = (it: NavItem) => { if (it.kind !== 'soon') setSel(it); };

  const renderContent = () => {
    if (sel.kind === 'catalog') return <GameCards initialPreset={sel.preset || ''} title={sel.label} />;
    switch (sel.key) {
      case 'regional': return <RegionalPriceExplorer />;
      case 'viewer': return <XboxProductViewer />;
      case 'variants': return <VariantExplorer />;
      case 'analytics': return <StatsCharts games={games} regionStats={regionStats} />;
      case 'history': return <PriceHistoryChart games={games} priceHistory={priceHistory} />;
      case 'gameflip': return <GameflipIntegration />;
      case 'kofi': return <KofiIntegration />;
      case 'social': return <SocialMediaIntegration selectedGames={selectedGameObjects} />;
      case 'sheets': return <GoogleSheetsIntegration onDataLoaded={() => {}} selectedGames={selectedGameObjects} onExportComplete={() => {}} />;
      case 'bulk': return <BulkUploadManager />;
      default: return <GameCards />;
    }
  };

  return (
    <div className={`min-h-screen bg-background text-foreground ${darkMode ? 'dark' : ''}`}>
      <div className="flex">
        <Sidebar active={sel.key} onSelect={onSelect} />

        <div className="flex-1 min-w-0">
          {/* Top bar */}
          <header className="sticky top-0 z-20 border-b bg-card/95 backdrop-blur">
            <div className="flex items-center justify-between px-4 sm:px-6 py-3">
              <div>
                <h1 className="text-lg font-bold">Cheap Xbox Games — Worldwide Price Comparison</h1>
                <p className="text-xs text-muted-foreground">
                  Datos oficiales de Microsoft Store · {games.length ? `${games.length} en memoria` : 'catálogo global'}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {progress.status !== 'Ready' && (
                  <Badge variant={progress.isActive ? 'default' : 'secondary'}>{progress.status}</Badge>
                )}
                {isElectron && (
                  <Badge variant="secondary"><Monitor className="h-3 w-3 mr-1" /> v{appVersion}</Badge>
                )}
                <Button variant="outline" size="icon" onClick={() => setDarkMode((v) => !v)}>
                  {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                </Button>
                <Button variant="outline" size="icon" onClick={() => setShowAdvancedSettings(true)}>
                  <Settings className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </header>

          <main className="px-4 sm:px-6 py-5 space-y-5">
            {/* Control de análisis (actualizar catálogo) solo en la vista de catálogo */}
            {sel.kind === 'catalog' && (
              <ScrapingControls
                progress={progress}
                onStartScraping={startScraping}
                onPauseScraping={pauseScraping}
                onStopScraping={stopScraping}
              />
            )}
            {renderContent()}
          </main>
        </div>
      </div>

      {/* Advanced Settings modal */}
      {showAdvancedSettings && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-card rounded-lg p-6 max-w-4xl w-full max-h-[80vh] overflow-y-auto">
            <AdvancedSettings />
            <Button onClick={() => setShowAdvancedSettings(false)} className="mt-4">Cerrar</Button>
          </div>
        </div>
      )}
    </div>
  );
}
