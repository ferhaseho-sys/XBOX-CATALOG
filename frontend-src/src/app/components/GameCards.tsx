import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Search, ExternalLink, ChevronLeft, ChevronRight, Loader2, SlidersHorizontal, X, Plus, Minus } from 'lucide-react';

const ATLAS_API = (import.meta as any).env?.VITE_ATLAS_API || 'http://127.0.0.1:8000';
const PAGE = 24;

const flag = (c: string) =>
  c && c.length === 2
    ? String.fromCodePoint(...[...c.toUpperCase()].map((ch) => 127397 + ch.charCodeAt(0)))
    : '';
const num = (v: any) => (v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 }));

let _regionNames: any = null;
try { _regionNames = new (Intl as any).DisplayNames(['es'], { type: 'region' }); } catch { /* noop */ }
const countryName = (c: string) => { try { return _regionNames?.of(c) || c; } catch { return c; } };

// Opciones de orden. Las que no tienen datos van deshabilitadas ("próximamente").
const SORTS: { value: string; label: string; off?: boolean }[] = [
  { value: 'savings', label: 'Mejor oferta (ahorro)' },
  { value: 'cheapest', label: 'Precio (más barato)' },
  { value: 'price_desc', label: 'Precio (más caro)' },
  { value: 'last_added', label: 'Agregados / Release' },
  { value: 'name', label: 'Nombre (A-Z)' },
  { value: 'gamepass', label: 'Game Pass primero (próximamente)', off: true },
  { value: 'metascore', label: 'Metascore (próximamente)', off: true },
];

// Presets. Los con datos funcionan; el resto se muestra deshabilitado.
const PRESETS: { value: string; label: string; off?: boolean }[] = [
  { value: '', label: 'Mostrar todo' },
  { value: 'discounts', label: 'Todas las ofertas' },
  { value: 'non_gold', label: 'Ofertas sin Gold' },
  { value: 'free', label: 'Solo Free (F2P)' },
  { value: 'play_anywhere', label: 'Solo Xbox Play Anywhere' },
  { value: 'series_x', label: 'Optimizado para Series X|S' },
  { value: 'dlc', label: 'Solo DLC / add-ons' },
  { value: 'games', label: 'Solo juegos' },
  { value: 'aaa', label: 'Solo AAA (próximamente)', off: true },
  { value: 'preview', label: 'Preview / Early Access (próximamente)', off: true },
  { value: 'ea', label: 'EA Play (próximamente)', off: true },
  { value: 'gamepass_in', label: 'En GAME PASS (próximamente)', off: true },
  { value: 'gamepass_ex', label: 'Excluir GAME PASS (próximamente)', off: true },
  { value: 'preorder', label: 'Solo Pre-Order (próximamente)', off: true },
  { value: 'giftcard', label: 'Países con Gift Card (próximamente)', off: true },
];

export function GameCards({ initialPreset = '', title }: { initialPreset?: string; title?: string }) {
  const [games, setGames] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [tooHeavy, setTooHeavy] = useState(false);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState('savings');
  const [preset, setPreset] = useState(initialPreset);
  const [term, setTerm] = useState('');
  const [searching, setSearching] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [rates, setRates] = useState<Record<string, number>>({});
  const [cur, setCur] = useState('USD');

  // países disponibles (con precios guardados) + incluir/excluir
  const [markets, setMarkets] = useState<string[]>([]);
  const [include, setInclude] = useState<string[]>([]);
  const [exclude, setExclude] = useState<string[]>([]);
  const [trending, setTrending] = useState<any[]>([]);

  useEffect(() => { setPreset(initialPreset); setPage(1); }, [initialPreset]);

  useEffect(() => {
    fetch(`${ATLAS_API}/api/fx`).then((r) => (r.ok ? r.json() : {})).then(setRates).catch(() => {});
    fetch(`${ATLAS_API}/api/catalog/markets`).then((r) => (r.ok ? r.json() : []))
      .then((d) => setMarkets((d as any[]).map((m) => m.market).filter(Boolean))).catch(() => {});
    fetch(`${ATLAS_API}/api/trending?limit=12`).then((r) => (r.ok ? r.json() : []))
      .then((d) => setTrending(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  const conv = (u: any) => (u == null ? null : cur === 'USD' || !rates[cur] ? Number(u) : Number(u) / rates[cur]);
  const CURRENCIES = ['USD', 'EUR', 'GBP', 'ARS', 'BRL', 'MXN', 'CLP', 'COP', 'PEN', 'TRY', 'RUB', 'UAH', 'INR', 'JPY', 'KRW', 'PLN', 'ZAR', 'NGN'];

  const pages = Math.max(1, Math.ceil(total / PAGE));

  const load = useCallback(async (p: number) => {
    setLoading(true); setTooHeavy(false);
    const qs = new URLSearchParams({ sort, page: String(p), limit: String(PAGE), preset });
    if (include.length) qs.set('include', include.join(','));
    if (exclude.length && !include.length) qs.set('exclude', exclude.join(','));
    try {
      const res = await fetch(`${ATLAS_API}/api/catalog?${qs}`);
      if (res.status === 503) { setTooHeavy(true); setGames([]); setTotal(0); setLoading(false); return; }
      const d = await res.json();
      setGames(Array.isArray(d.items) ? d.items : []);
      setTotal(d.total || 0);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch { setGames([]); setTotal(0); }
    setLoading(false);
  }, [sort, preset, include, exclude]);

  // recargar cuando cambian orden/preset/países (vuelve a página 1)
  useEffect(() => {
    if (searching) return;
    setPage(1);
    load(1);
  }, [sort, preset, include, exclude, load, searching]);

  const goPage = (p: number) => { if (p < 1 || p > pages) return; setPage(p); load(p); };

  const doSearch = async () => {
    const t = term.trim();
    if (!t) { setSearching(false); setPage(1); load(1); return; }
    setSearching(true); setLoading(true); setTooHeavy(false);
    try {
      const found = await fetch(`${ATLAS_API}/api/search?term=${encodeURIComponent(t)}&limit=40`)
        .then((r) => (r.ok ? r.json() : []));
      setGames((found as any[]).map((g) => ({
        product_id: g.product_id, title: g.title, image_boxart: g.image_boxart,
        publisher: g.publisher, product_type: g.product_type, kind: g.kind, is_demo: g.is_demo,
        on_pc: g.on_pc, on_xbox: g.on_xbox, us_currency: g.currency, us_list: g.list_price,
        us_usd: g.price_usd, us_disc: g.discount_pct, cheapest: null, release_date: null,
        short_desc: null, console_gen: [], has_addons: false,
      })));
      setTotal(0);
    } catch { setGames([]); }
    setLoading(false);
  };

  const addCountry = (list: 'in' | 'ex', code: string) => {
    if (!code) return;
    if (list === 'in') { setExclude((e) => e.filter((c) => c !== code)); setInclude((i) => i.includes(code) ? i : [...i, code]); }
    else { setInclude((i) => i.filter((c) => c !== code)); setExclude((e) => e.includes(code) ? e : [...e, code]); }
  };
  const removeCountry = (list: 'in' | 'ex', code: string) =>
    (list === 'in' ? setInclude : setExclude)((arr: string[]) => arr.filter((c) => c !== code));

  const availableCountries = useMemo(
    () => markets.filter((m) => !include.includes(m) && !exclude.includes(m))
      .map((m) => ({ code: m, name: countryName(m) }))
      .sort((a, b) => a.name.localeCompare(b.name)),
    [markets, include, exclude]);

  const badgesOf = (g: any) => {
    const out: string[] = [];
    const cg = g.console_gen || [];
    if (Array.isArray(cg) && cg.includes('ConsoleGen9')) out.push('Series X|S');
    if (g.on_pc && g.on_xbox) out.push('Play Anywhere');
    else if (g.on_pc) out.push('PC');
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

  const activeCountryFilter = include.length > 0 || exclude.length > 0;

  return (
    <div className="space-y-4">
      {title && <h2 className="text-xl font-bold">{title}</h2>}

      {/* Barra de filtros comunes */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input className="pl-9" placeholder="Buscar juego por título…" value={term}
            onChange={(e) => setTerm(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && doSearch()} />
        </div>
        <Button onClick={doSearch} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Go!'}
        </Button>
        <select value={sort} onChange={(e) => setSort(e.target.value)} disabled={searching}
          className="border border-border rounded-md bg-background px-2 py-2 text-sm" title="Ordenar">
          {SORTS.map((s) => <option key={s.value} value={s.value} disabled={s.off}>{s.label}</option>)}
        </select>
        <Button variant={showFilters ? 'default' : 'outline'} onClick={() => setShowFilters((v) => !v)}>
          <SlidersHorizontal className="h-4 w-4 mr-1" /> Filtros
        </Button>
        <select value={cur} onChange={(e) => setCur(e.target.value)} title="Moneda de referencia"
          className="border border-border rounded-md bg-background px-2 py-2 text-sm">
          {CURRENCIES.filter((c) => c === 'USD' || rates[c]).map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* Panel de filtros avanzados */}
      {showFilters && (
        <Card className="p-4 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-semibold"><SlidersHorizontal className="h-4 w-4" /> Filtros avanzados</div>
            <Button variant="ghost" size="icon" onClick={() => setShowFilters(false)}><X className="h-4 w-4" /></Button>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            {/* Preset filter */}
            <div>
              <label className="text-sm font-medium">Preset</label>
              <select value={preset} onChange={(e) => setPreset(e.target.value)}
                className="mt-1 w-full border border-border rounded-md bg-background px-2 py-2 text-sm">
                {PRESETS.map((p) => <option key={p.value} value={p.value} disabled={p.off}>{p.label}</option>)}
              </select>
              <p className="text-xs text-muted-foreground mt-2">
                Los ítems “(próximamente)” aún no tienen datos (Game Pass, Metascore, EA, AAA).
              </p>
            </div>
            {/* Included countries */}
            <CountryPanel title="Incluir países" tone="in" list={include}
              onRemove={(c) => removeCountry('in', c)} />
            {/* Excluded countries */}
            <CountryPanel title="Excluir países" tone="ex" list={exclude}
              onRemove={(c) => removeCountry('ex', c)} disabled={include.length > 0} />
          </div>
          {/* selector para agregar país */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">Agregar país:</span>
            <select id="country-picker" className="border border-border rounded-md bg-background px-2 py-1.5 text-sm min-w-[200px]" defaultValue="">
              <option value="" disabled>Elegí un país…</option>
              {availableCountries.map((c) => <option key={c.code} value={c.code}>{flag(c.code)} {c.name} ({c.code})</option>)}
            </select>
            <Button size="sm" variant="outline" onClick={() => {
              const el = document.getElementById('country-picker') as HTMLSelectElement;
              if (el?.value) { addCountry('in', el.value); el.value = ''; }
            }}><Plus className="h-3 w-3 mr-1" /> Incluir</Button>
            <Button size="sm" variant="outline" disabled={include.length > 0} onClick={() => {
              const el = document.getElementById('country-picker') as HTMLSelectElement;
              if (el?.value) { addCountry('ex', el.value); el.value = ''; }
            }}><Minus className="h-3 w-3 mr-1" /> Excluir</Button>
            {activeCountryFilter && (
              <Button size="sm" variant="ghost" onClick={() => { setInclude([]); setExclude([]); }}>Limpiar países</Button>
            )}
          </div>
          {activeCountryFilter && (
            <p className="text-xs text-amber-600 dark:text-amber-500">
              Con países filtrados se recalcula la región más barata en vivo (puede tardar unos segundos).
            </p>
          )}
        </Card>
      )}

      {/* Resumen de resultados */}
      {!searching && !tooHeavy && (
        <div className="text-sm text-muted-foreground">
          {total.toLocaleString()} resultados{preset ? ` · ${PRESETS.find((p) => p.value === preset)?.label}` : ''}
          {activeCountryFilter ? ` · ${include.length ? 'incluyendo' : 'excluyendo'} ${(include.length ? include : exclude).length} países` : ''}
        </div>
      )}

      {loading && <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Cargando…</div>}
      {tooHeavy && (
        <Card className="p-4 text-sm text-amber-600 dark:text-amber-500">
          La selección de países es demasiado amplia para el plan free. Probá <b>incluir</b> pocos países
          (en vez de excluir muchos), o reducí la selección.
        </Card>
      )}

      {/* Tarjetas */}
      <div className="space-y-3">
        {games.map((g) => {
          const c = g.cheapest;
          const sp = savePct(g);
          return (
            <Card key={g.product_id} className="p-3">
              <div className="flex gap-4">
                {g.image_boxart ? (
                  <img src={g.image_boxart} alt={g.title} loading="lazy"
                    className="w-[90px] h-[126px] object-cover rounded-md bg-muted flex-shrink-0"
                    onError={(e: any) => { e.currentTarget.onerror = null; e.currentTarget.className += ' opacity-0'; }} />
                ) : (
                  <div className="w-[90px] h-[126px] rounded-md bg-muted flex items-center justify-center text-2xl font-bold text-muted-foreground flex-shrink-0">
                    {(g.title || '?').slice(0, 1)}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <a className="font-semibold hover:underline truncate"
                      href={`https://www.xbox.com/games/store/_/${g.product_id}`} target="_blank" rel="noopener noreferrer">
                      {g.title}
                    </a>
                    {g.is_demo && <Badge variant="destructive" className="text-[0.65rem]">Demo</Badge>}
                    {badgesOf(g).map((b) => <Badge key={b} variant="secondary" className="text-[0.65rem]">{b}</Badge>)}
                  </div>
                  {g.release_date && <div className="text-xs text-muted-foreground mt-0.5">Release: {g.release_date}</div>}
                  {g.short_desc && <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{g.short_desc}</p>}
                  <div className="flex gap-2 mt-2">
                    <Button size="sm" variant="outline" asChild>
                      <a href={`https://www.xbox.com/games/store/_/${g.product_id}`} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-3 w-3 mr-1" /> Xbox Store
                      </a>
                    </Button>
                  </div>
                </div>
                <div className="flex gap-3 flex-shrink-0">
                  <PriceBox flagCode="US" name="USA" currency={g.us_currency} local={g.us_list} refVal={conv(g.us_usd)} refCur={cur} disc={g.us_disc} />
                  {c && (
                    <PriceBox flagCode={c.market} name={c.market} currency={c.currency} local={c.list_price}
                      refVal={conv(c.price_usd)} refCur={cur} disc={c.discount_pct} save={sp}
                      dealUntil={c.on_sale ? c.sale_ends : null} highlight />
                  )}
                </div>
              </div>
            </Card>
          );
        })}
        {!loading && !tooHeavy && games.length === 0 && (
          <div className="text-sm text-muted-foreground py-8 text-center">Sin resultados.</div>
        )}
      </div>

      {/* Paginación numerada */}
      {!searching && pages > 1 && (
        <Pagination page={page} pages={pages} loading={loading} onGo={goPage} />
      )}

      {/* What's Trending */}
      {trending.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">What's Trending</h3>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-9 gap-3">
            {trending.map((t) => (
              <a key={t.product_id} href={`https://www.xbox.com/games/store/_/${t.product_id}`}
                target="_blank" rel="noopener noreferrer" className="group text-center">
                {t.image_boxart ? (
                  <img src={t.image_boxart} alt={t.title} loading="lazy"
                    className="w-full aspect-[3/4] object-cover rounded-md bg-muted group-hover:opacity-90" />
                ) : (
                  <div className="w-full aspect-[3/4] rounded-md bg-muted flex items-center justify-center font-bold text-muted-foreground">
                    {(t.title || '?').slice(0, 1)}
                  </div>
                )}
                <div className="text-xs mt-1 line-clamp-2 group-hover:underline">{t.title}</div>
                {t.cheapest_usd != null && (
                  <div className="text-[0.7rem] text-muted-foreground">desde ${Number(t.cheapest_usd).toFixed(2)} {flag(t.cheapest_market)}</div>
                )}
              </a>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// Panel de país (chips removibles), estilo xbox-now (Included/Excluded)
function CountryPanel({ title, tone, list, onRemove, disabled }: any) {
  return (
    <div className={`rounded-md border p-3 ${tone === 'in' ? 'border-green-600/40' : 'border-red-600/40'} ${disabled ? 'opacity-50' : ''}`}>
      <div className="font-medium text-sm mb-2">{title}</div>
      {list.length === 0 ? (
        <div className="text-xs text-muted-foreground">{disabled ? 'Desactivado mientras haya países incluidos' : 'Ninguno'}</div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {list.map((c: string) => (
            <span key={c} className="inline-flex items-center gap-1 text-xs bg-muted rounded-full px-2 py-0.5">
              {flag(c)} {c}
              <button onClick={() => onRemove(c)} className="hover:text-destructive"><X className="h-3 w-3" /></button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// Paginación numerada con ventana alrededor de la página actual
function Pagination({ page, pages, loading, onGo }: any) {
  const win = 2;
  const nums: number[] = [];
  for (let i = Math.max(1, page - win); i <= Math.min(pages, page + win); i++) nums.push(i);
  return (
    <div className="flex items-center justify-center gap-1 py-4 flex-wrap">
      <Button variant="outline" size="sm" onClick={() => onGo(page - 1)} disabled={page <= 1 || loading}>
        <ChevronLeft className="h-4 w-4" />
      </Button>
      {nums[0] > 1 && (<><Button variant="outline" size="sm" onClick={() => onGo(1)} disabled={loading}>1</Button><span className="px-1 text-muted-foreground">…</span></>)}
      {nums.map((n) => (
        <Button key={n} variant={n === page ? 'default' : 'outline'} size="sm" onClick={() => onGo(n)} disabled={loading}>{n}</Button>
      ))}
      {nums[nums.length - 1] < pages && (<><span className="px-1 text-muted-foreground">…</span><Button variant="outline" size="sm" onClick={() => onGo(pages)} disabled={loading}>{pages}</Button></>)}
      <Button variant="outline" size="sm" onClick={() => onGo(page + 1)} disabled={page >= pages || loading}>
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  );
}

function PriceBox({ flagCode, name, currency, local, refVal, refCur, disc, save, dealUntil, highlight }: any) {
  const ref = refVal == null ? '—'
    : refCur === 'USD' ? `$${Number(refVal).toFixed(2)}`
    : `${refCur} ${Number(refVal).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  return (
    <div className={`min-w-[140px] rounded-md border p-2 ${highlight ? 'border-green-600/40 bg-green-600/5' : 'border-border'}`}>
      <div className="text-xs text-muted-foreground flex items-center gap-1"><span>{flag(flagCode)}</span> {name}</div>
      <div className="font-bold tabular-nums">{ref}</div>
      {local != null && <div className="text-xs tabular-nums text-muted-foreground">{currency} {num(local)}</div>}
      {disc > 0 && <Badge className="mt-1 text-[0.6rem]" variant="destructive">-{disc}%</Badge>}
      {save > 0 && <div className="text-[0.7rem] text-green-500 mt-0.5">ahorrás {save}%</div>}
      {dealUntil && <div className="text-[0.65rem] text-muted-foreground mt-0.5">hasta {String(dealUntil).slice(0, 10)}</div>}
    </div>
  );
}
