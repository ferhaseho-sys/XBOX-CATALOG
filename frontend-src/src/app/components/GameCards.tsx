import { useState, useEffect, useCallback } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Search, ExternalLink, ChevronLeft, ChevronRight, Loader2, Info } from 'lucide-react';

const ATLAS_API = (import.meta as any).env?.VITE_ATLAS_API || 'http://127.0.0.1:8000';
const PAGE = 24;

const flag = (c: string) =>
  c && c.length === 2
    ? String.fromCodePoint(...[...c.toUpperCase()].map((ch) => 127397 + ch.charCodeAt(0)))
    : '';
const num = (v: any) => (v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 }));
const usd = (v: any) => (v == null ? '' : `$${Number(v).toFixed(2)}`);

// Catálogo estilo xbox-now: tarjeta con portada + descripción + 2 columnas de
// precio (US y la región más barata) + ahorro + oferta. Paginación server-side.
export function GameCards() {
  const [games, setGames] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState('savings');
  const [dealsOnly, setDealsOnly] = useState(false);
  const [term, setTerm] = useState('');
  const [searching, setSearching] = useState(false);
  const [rates, setRates] = useState<Record<string, number>>({});
  const [cur, setCur] = useState('USD');

  useEffect(() => {
    fetch(`${ATLAS_API}/api/fx`).then((r) => (r.ok ? r.json() : {})).then(setRates).catch(() => {});
  }, []);
  // convierte un valor en USD a la moneda elegida (usd_rate = USD por 1 unidad)
  const conv = (u: any) => (u == null ? null : cur === 'USD' || !rates[cur] ? Number(u) : Number(u) / rates[cur]);
  const CURRENCIES = ['USD', 'EUR', 'GBP', 'ARS', 'BRL', 'MXN', 'CLP', 'COP', 'PEN', 'TRY', 'RUB', 'UAH', 'INR', 'JPY', 'KRW', 'PLN', 'ZAR', 'NGN'];

  const load = useCallback(async (p: number, s: string, dealsMin: number) => {
    setLoading(true);
    try {
      const d = await fetch(`${ATLAS_API}/api/catalog?sort=${s}&page=${p}&min_savings=${dealsMin}&limit=${PAGE}`)
        .then((r) => (r.ok ? r.json() : []));
      setGames(Array.isArray(d) ? d : []);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch {
      setGames([]);
    }
    setLoading(false);
  }, []);

  // recargar cuando cambia orden/filtro (vuelve a página 1)
  useEffect(() => {
    if (searching) return;
    setPage(1);
    load(1, sort, dealsOnly ? 30 : 0);
  }, [sort, dealsOnly, load, searching]);

  const goPage = (p: number) => { setPage(p); load(p, sort, dealsOnly ? 30 : 0); };

  const doSearch = async () => {
    const t = term.trim();
    if (!t) { setSearching(false); setPage(1); load(1, sort, dealsOnly ? 30 : 0); return; }
    setSearching(true);
    setLoading(true);
    try {
      const found = await fetch(`${ATLAS_API}/api/search?term=${encodeURIComponent(t)}&limit=40`)
        .then((r) => (r.ok ? r.json() : []));
      // buscar trae metadata + us price; lo adaptamos al shape de catálogo
      setGames((found as any[]).map((g) => ({
        product_id: g.product_id, title: g.title, image_boxart: g.image_boxart,
        publisher: g.publisher, product_type: g.product_type, kind: g.kind, is_demo: g.is_demo,
        us_currency: g.currency, us_list: g.list_price, us_usd: g.price_usd,
        us_disc: g.discount_pct, cheapest: null, release_date: null, short_desc: null,
        console_gen: [], has_addons: false,
      })));
    } catch { setGames([]); }
    setLoading(false);
  };

  const badgesOf = (g: any) => {
    const out: string[] = [];
    const cg = g.console_gen || [];
    if (Array.isArray(cg) && cg.includes('ConsoleGen9')) out.push('Series X|S');
    // categoría legible (Juego/DLC/Moneda/Suscripción/Gift card); no repetir "Juego"
    const kind = g.kind || (g.product_type && g.product_type !== 'Game' ? g.product_type : '');
    if (kind && kind !== 'Juego') out.push(kind);
    if (g.has_addons) out.push('+ Add-ons');
    return out;
  };
  const savePct = (g: any) => {
    const c = g.cheapest;
    if (!c || !g.us_usd || !c.price_usd) return 0;
    return Math.round((1 - c.price_usd / g.us_usd) * 100);
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Buscar juego por título…"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && doSearch()}
          />
        </div>
        <Button onClick={doSearch} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Buscar'}
        </Button>
        <select
          value={cur}
          onChange={(e) => setCur(e.target.value)}
          className="border border-border rounded-md bg-background px-2 text-sm"
          title="Moneda de referencia"
        >
          {CURRENCIES.filter((c) => c === 'USD' || rates[c]).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* Orden + solo ofertas */}
      <div className="flex items-center gap-3 flex-wrap text-sm">
        <span className="text-muted-foreground">Ordenar:</span>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="border border-border rounded-md bg-background px-2 py-1"
          disabled={searching}
        >
          <option value="savings">Mayor ahorro</option>
          <option value="cheapest">Más barato (USD)</option>
          <option value="name">Nombre (A-Z)</option>
        </select>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input type="checkbox" checked={dealsOnly} onChange={(e) => setDealsOnly(e.target.checked)} disabled={searching} />
          <span>Solo ofertas grandes (≥30%)</span>
        </label>
        {searching && <span className="text-muted-foreground">(resultados de búsqueda)</span>}
      </div>

      {loading && <div className="text-sm text-muted-foreground">Cargando…</div>}

      <div className="space-y-3">
        {games.map((g) => {
          const c = g.cheapest;
          const sp = savePct(g);
          return (
            <Card key={g.product_id} className="p-3">
              <div className="flex gap-4">
                {/* Portada (o placeholder si no hay imagen) */}
                {g.image_boxart ? (
                  <img
                    src={g.image_boxart}
                    alt={g.title}
                    className="w-[90px] h-[126px] object-cover rounded-md bg-muted flex-shrink-0"
                    onError={(e: any) => { e.currentTarget.onerror = null; e.currentTarget.src = ''; e.currentTarget.className += ' opacity-0'; }}
                    loading="lazy"
                  />
                ) : (
                  <div className="w-[90px] h-[126px] rounded-md bg-muted flex items-center justify-center text-2xl font-bold text-muted-foreground flex-shrink-0">
                    {(g.title || '?').slice(0, 1)}
                  </div>
                )}
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <a
                      className="font-semibold hover:underline truncate"
                      href={`https://www.xbox.com/games/store/_/${g.product_id}`}
                      target="_blank" rel="noopener noreferrer"
                    >
                      {g.title}
                    </a>
                    {g.is_demo && (
                      <Badge variant="destructive" className="text-[0.65rem]">Demo</Badge>
                    )}
                    {badgesOf(g).map((b) => (
                      <Badge key={b} variant="secondary" className="text-[0.65rem]">{b}</Badge>
                    ))}
                  </div>
                  {g.release_date && (
                    <div className="text-xs text-muted-foreground mt-0.5">Release: {g.release_date}</div>
                  )}
                  {g.short_desc && (
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{g.short_desc}</p>
                  )}
                  <div className="flex gap-2 mt-2">
                    <Button size="sm" variant="outline" asChild>
                      <a href={`https://www.xbox.com/games/store/_/${g.product_id}`} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-3 w-3 mr-1" /> Xbox Store
                      </a>
                    </Button>
                  </div>
                </div>
                {/* Precios: US + más barata */}
                <div className="flex gap-3 flex-shrink-0">
                  <PriceBox flagCode="US" name="USA" currency={g.us_currency} local={g.us_list} refVal={conv(g.us_usd)} refCur={cur} disc={g.us_disc} />
                  {c && (
                    <PriceBox
                      flagCode={c.market} name={c.market} currency={c.currency}
                      local={c.list_price} refVal={conv(c.price_usd)} refCur={cur} disc={c.discount_pct}
                      save={sp} dealUntil={c.on_sale ? c.sale_ends : null}
                      highlight
                    />
                  )}
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Paginación */}
      {!searching && (
        <div className="flex items-center justify-center gap-3 py-4">
          <Button variant="outline" size="sm" onClick={() => goPage(page - 1)} disabled={page <= 1 || loading}>
            <ChevronLeft className="h-4 w-4" /> Anterior
          </Button>
          <span className="text-sm text-muted-foreground">Página {page}</span>
          <Button variant="outline" size="sm" onClick={() => goPage(page + 1)} disabled={games.length < PAGE || loading}>
            Siguiente <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

function PriceBox({ flagCode, name, currency, local, refVal, refCur, disc, save, dealUntil, highlight }: any) {
  const ref = refVal == null ? '—'
    : refCur === 'USD' ? `$${Number(refVal).toFixed(2)}`
    : `${refCur} ${Number(refVal).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  return (
    <div className={`min-w-[140px] rounded-md border p-2 ${highlight ? 'border-green-600/40 bg-green-600/5' : 'border-border'}`}>
      <div className="text-xs text-muted-foreground flex items-center gap-1">
        <span>{flag(flagCode)}</span> {name}
      </div>
      <div className="font-bold tabular-nums">{ref}</div>
      {local != null && (
        <div className="text-xs tabular-nums text-muted-foreground">{currency} {num(local)}</div>
      )}
      {disc > 0 && <Badge className="mt-1 text-[0.6rem]" variant="destructive">-{disc}%</Badge>}
      {save > 0 && <div className="text-[0.7rem] text-green-500 mt-0.5">ahorrás {save}%</div>}
      {dealUntil && <div className="text-[0.65rem] text-muted-foreground mt-0.5">hasta {String(dealUntil).slice(0, 10)}</div>}
    </div>
  );
}
