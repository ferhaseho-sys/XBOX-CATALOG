import {
  Gamepad2, Package, Tag, LayoutList, Star, Crown, Disc, Layers, LineChart,
  CreditCard, HelpCircle, Globe, Search, BarChart3, TrendingUp, Newspaper,
  MessageSquare, Coffee, Share2, FileSpreadsheet, Zap,
} from 'lucide-react';

export type NavItem = {
  key: string;
  label: string;
  icon: any;
  kind: 'catalog' | 'view' | 'soon';
  preset?: string;
};

// Grupos del sidebar, estilo xbox-now. Los "soon" no tienen datos aún.
export const NAV_GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Catálogo',
    items: [
      { key: 'cat', label: 'Game Comparison', icon: Gamepad2, kind: 'catalog', preset: '' },
      { key: 'cat-dlc', label: 'DLC Comparison', icon: Package, kind: 'catalog', preset: 'dlc' },
      { key: 'cat-deals', label: 'Deals & Discounts', icon: Tag, kind: 'catalog', preset: 'discounts' },
      { key: 'cat-free', label: 'Free Games', icon: Star, kind: 'catalog', preset: 'free' },
      { key: 'cat-xpa', label: 'Play Anywhere', icon: Layers, kind: 'catalog', preset: 'play_anywhere' },
      { key: 'cat-sx', label: 'Optimized Series X|S', icon: Disc, kind: 'catalog', preset: 'series_x' },
    ],
  },
  {
    title: 'Herramientas',
    items: [
      { key: 'regional', label: 'Precios por país', icon: Globe, kind: 'view' },
      { key: 'viewer', label: 'Producto', icon: Search, kind: 'view' },
      { key: 'variants', label: 'Variantes', icon: Layers, kind: 'view' },
      { key: 'analytics', label: 'Analytics', icon: BarChart3, kind: 'view' },
      { key: 'history', label: 'Historial', icon: LineChart, kind: 'view' },
    ],
  },
  {
    title: 'Integraciones',
    items: [
      { key: 'gameflip', label: 'Gameflip', icon: Gamepad2, kind: 'view' },
      { key: 'kofi', label: 'Ko-fi', icon: Coffee, kind: 'view' },
      { key: 'social', label: 'Social', icon: Share2, kind: 'view' },
      { key: 'sheets', label: 'Sheets', icon: FileSpreadsheet, kind: 'view' },
      { key: 'bulk', label: 'Bulk Upload', icon: Package, kind: 'view' },
    ],
  },
  {
    title: 'Próximamente',
    items: [
      { key: 's-gp', label: 'GAME PASS Games', icon: Crown, kind: 'soon' },
      { key: 's-overview', label: 'Deal Overview', icon: LayoutList, kind: 'soon' },
      { key: 's-recent', label: 'Recent Price Changes', icon: TrendingUp, kind: 'soon' },
      { key: 's-360', label: 'Xbox 360 Games', icon: Gamepad2, kind: 'soon' },
      { key: 's-subs', label: 'Compare Subscriptions', icon: Layers, kind: 'soon' },
      { key: 's-gift', label: 'Gift Card Shops', icon: CreditCard, kind: 'soon' },
      { key: 's-reviews', label: 'Reviews', icon: MessageSquare, kind: 'soon' },
      { key: 's-news', label: 'News', icon: Newspaper, kind: 'soon' },
      { key: 's-faq', label: 'Tutorial & FAQ', icon: HelpCircle, kind: 'soon' },
    ],
  },
];

export function Sidebar({ active, onSelect }: { active: string; onSelect: (it: NavItem) => void }) {
  return (
    <aside className="w-60 flex-shrink-0 bg-card border-r min-h-screen sticky top-0 h-screen overflow-y-auto">
      <div className="flex items-center gap-2 px-4 py-4 border-b sticky top-0 bg-card z-10">
        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
          <Zap className="h-5 w-5 text-primary-foreground" />
        </div>
        <div className="font-bold leading-tight">Xbox Price<br />Atlas</div>
      </div>
      <nav className="py-2">
        {NAV_GROUPS.map((g) => (
          <div key={g.title} className="mb-2">
            <div className="px-4 py-1.5 text-[0.7rem] uppercase tracking-wider text-muted-foreground">{g.title}</div>
            {g.items.map((it) => {
              const Icon = it.icon;
              const isActive = active === it.key;
              const soon = it.kind === 'soon';
              return (
                <button
                  key={it.key}
                  disabled={soon}
                  onClick={() => onSelect(it)}
                  title={soon ? 'Próximamente' : it.label}
                  className={`w-full flex items-center gap-2.5 px-4 py-2 text-sm text-left transition-colors
                    ${isActive ? 'bg-primary/10 text-primary border-l-2 border-primary font-medium' : 'border-l-2 border-transparent'}
                    ${soon ? 'opacity-40 cursor-not-allowed' : 'hover:bg-muted'}`}
                >
                  <Icon className="h-4 w-4 flex-shrink-0" />
                  <span className="truncate">{it.label}</span>
                  {soon && <span className="ml-auto text-[0.6rem] text-muted-foreground">pronto</span>}
                </button>
              );
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}
