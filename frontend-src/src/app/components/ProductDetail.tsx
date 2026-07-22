import { useState, useEffect, useMemo } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ArrowLeft, ExternalLink, Loader2, Globe, Star } from 'lucide-react';

const ATLAS_API = (import.meta as any).env?.VITE_ATLAS_API || 'http://127.0.0.1:8000';

const flag = (c: string) =>
  c && c.length === 2
    ? String.fromCodePoint(...[...c.toUpperCase()].map((ch) => 127397 + ch.charCodeAt(0)))
    : '';
let _rn: any = null;
try { _rn = new (Intl as any).DisplayNames(['es'], { type: 'region' }); } catch { /* noop */ }
const countryName = (c: string) => { try { return _rn?.of(c) || c; } catch { return c; } };
const CURRENCIES = ['USD', 'EUR', 'GBP', 'ARS', 'BRL', 'MXN', 'CLP', 'COP', 'PEN', 'TRY', 'RUB', 'UAH', 'INR', 'JPY', 'KRW', 'PLN', 'ZAR', 'NGN'];
const STORE = (id: string) => `https://www.xbox.com/games/store/_/${id}`;

export function ProductDetail({ productId, onBack, onOpen }: { productId: string; onBack: () => void; onOpen?: (id: string) => void }) {
  const [p, setP] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [rates, setRates] = useState<Record<string, number>>({});
  const [cur, setCur] = useState('USD');
  const [expanded, setExpanded] = useState(false);
  const [live, setLive] = useState<any[] | null>(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveErr, setLiveErr] = useState('');
  const [media, setMedia] = useState<any>(null);
  const [reviews, setReviews] = useState<any>(null);
  const [related, setRelated] = useState<any[]>([]);
  const [shot, setShot] = useState(0); // screenshot activo

  const open = (id: string) => (onOpen ? onOpen(id) : window.open(`/product/${id}`, '_blank'));

  useEffect(() => {
    setLoading(true); setLive(null); setLiveErr(''); setMedia(null); setReviews(null); setRelated([]); setShot(0);
    window.scrollTo({ top: 0 });
    // 1) ficha desde la DB; si no está, fallback a la consulta EN VIVO (cualquier producto de MS)
    fetch(`${ATLAS_API}/api/product/${productId}`).then((r) => (r.ok ? r.json() : null))
      .then(async (d) => {
        if (d) { setP(d); return; }
        const lv = await fetch(`${ATLAS_API}/api/live/product/${productId}`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
        setP(lv ? { product_id: productId, title: lv.title, prices: lv.prices || [], variants: lv.variants || [] } : null);
        if (lv?.prices) setLive(lv.prices);
      })
      .catch(() => setP(null)).finally(() => setLoading(false));
    // 2) medios ricos (screenshots/tráiler/capacidades) + reseñas + relacionados (en vivo/scrape; andan en Railway)
    fetch(`${ATLAS_API}/api/product/${productId}/media`).then((r) => (r.ok ? r.json() : null)).then(setMedia).catch(() => {});
    fetch(`${ATLAS_API}/api/reviews/${productId}`).then((r) => (r.ok ? r.json() : null)).then(setReviews).catch(() => {});
    fetch(`${ATLAS_API}/api/related/${productId}`).then((r) => (r.ok ? r.json() : [])).then((d) => setRelated(Array.isArray(d) ? d : [])).catch(() => {});
  }, [productId]);

  useEffect(() => {
    fetch(`${ATLAS_API}/api/fx`).then((r) => (r.ok ? r.json() : {})).then(setRates).catch(() => {});
  }, []);

  const conv = (u: any) => (u == null ? null : cur === 'USD' || !rates[cur] ? Number(u) : Number(u) / rates[cur]);
  const fmtRef = (u: any) => {
    const v = conv(u);
    if (v == null) return '—';
    return cur === 'USD' ? `$${v.toFixed(2)}` : `${cur} ${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  };

  // filas de la tabla: precios guardados (o live si se cargó), ordenados por USD
  const rows = useMemo(() => {
    const base = live || (p?.prices || []);
    return [...base]
      .filter((r: any) => r.price_usd != null && Number(r.list_price) > 0)
      .sort((a: any, b: any) => Number(a.price_usd) - Number(b.price_usd));
  }, [p, live]);

  const usUsd = useMemo(() => {
    const us = (live || p?.prices || []).find((r: any) => r.market === 'US');
    return us?.price_usd != null ? Number(us.price_usd) : null;
  }, [p, live]);

  const badges = useMemo(() => {
    if (!p) return [];
    const out: string[] = [];
    if (Array.isArray(p.console_gen) && p.console_gen.includes('ConsoleGen9')) out.push('Series X|S');
    if (p.on_pc && p.on_xbox) out.push('Play Anywhere');
    else if (p.on_pc) out.push('PC');
    if (p.kind && p.kind !== 'Juego') out.push(p.kind);
    if (p.has_addons) out.push('+ Add-ons');
    if (p.is_demo) out.push('Demo');
    return out;
  }, [p]);

  const loadLive = async () => {
    setLiveLoading(true); setLiveErr('');
    try {
      const d = await fetch(`${ATLAS_API}/api/live/product/${productId}`).then((r) => (r.ok ? r.json() : null));
      if (d && Array.isArray(d.prices) && d.prices.length) setLive(d.prices);
      else setLiveErr('No se pudo cargar la consulta en vivo.');
    } catch { setLiveErr('No se pudo cargar la consulta en vivo.'); }
    setLiveLoading(false);
  };

  if (loading) return <div className="flex items-center gap-2 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Cargando ficha…</div>;
  if (!p) return (
    <div className="space-y-3">
      <Button variant="outline" size="sm" onClick={onBack}><ArrowLeft className="h-4 w-4 mr-1" /> Volver</Button>
      <div className="text-muted-foreground">No se encontró el producto.</div>
    </div>
  );

  const desc = p.description || p.short_desc || media?.description || '';
  const showDesc = expanded ? desc : desc.slice(0, 600);
  const shots: string[] = media?.screenshots || [];

  return (
    <div className="space-y-5">
      <Button variant="outline" size="sm" onClick={onBack}><ArrowLeft className="h-4 w-4 mr-1" /> Volver al catálogo</Button>

      {/* Cabecera */}
      <Card className="overflow-hidden">
        {p.image_hero && (
          <div className="relative h-40 sm:h-52 bg-muted">
            <img src={p.image_hero} alt="" className="w-full h-full object-cover opacity-40" />
            <div className="absolute inset-0 bg-gradient-to-t from-card to-transparent" />
          </div>
        )}
        <div className="p-4 flex gap-4 -mt-16 sm:-mt-20 relative">
          {p.image_boxart ? (
            <img src={p.image_boxart} alt={p.title} className="w-[110px] h-[154px] object-cover rounded-md bg-muted flex-shrink-0 shadow-lg" />
          ) : (
            <div className="w-[110px] h-[154px] rounded-md bg-muted flex items-center justify-center text-3xl font-bold text-muted-foreground flex-shrink-0">{(p.title || '?').slice(0, 1)}</div>
          )}
          <div className="flex-1 min-w-0 pt-16 sm:pt-20">
            <h1 className="text-2xl font-bold">{p.title}</h1>
            <div className="text-sm text-muted-foreground">
              {p.publisher || p.developer}{p.kind ? ` · ${p.kind}` : ''}{p.release_date ? ` · ${String(p.release_date).slice(0, 10)}` : ''}
            </div>
            <div className="flex items-center gap-2 flex-wrap mt-2">
              {p.avg_rating != null && (
                <span className="inline-flex items-center gap-1 text-sm"><Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" /> {Number(p.avg_rating).toFixed(1)} {p.rating_count ? <span className="text-muted-foreground">({p.rating_count})</span> : null}</span>
              )}
              {badges.map((b) => <Badge key={b} variant={b === 'Demo' ? 'destructive' : 'secondary'} className="text-[0.7rem]">{b}</Badge>)}
            </div>
            <div className="flex gap-2 mt-3">
              <Button size="sm" asChild>
                <a href={STORE(p.product_id)} target="_blank" rel="noopener noreferrer"><ExternalLink className="h-3.5 w-3.5 mr-1" /> Xbox Store</a>
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Descripción */}
      {desc && (
        <Card className="p-4">
          <h2 className="font-semibold mb-2">Descripción</h2>
          <p className="text-sm text-muted-foreground whitespace-pre-line">{showDesc}{!expanded && desc.length > 600 ? '…' : ''}</p>
          {desc.length > 600 && (
            <button className="text-sm text-primary mt-2" onClick={() => setExpanded((v) => !v)}>{expanded ? 'Mostrar menos' : 'Mostrar más'}</button>
          )}
        </Card>
      )}

      {/* Galería de screenshots + capacidades */}
      {(shots.length > 0 || (media?.capabilities?.length)) && (
        <Card className="p-4 space-y-3">
          {shots.length > 0 && (
            <div>
              <img src={shots[shot]} alt="" className="w-full max-h-[420px] object-cover rounded-md bg-muted" />
              {shots.length > 1 && (
                <div className="flex gap-2 mt-2 overflow-x-auto pb-1">
                  {shots.map((s, i) => (
                    <img key={i} src={s} alt="" onClick={() => setShot(i)}
                      className={`h-14 w-24 object-cover rounded cursor-pointer flex-shrink-0 ${i === shot ? 'ring-2 ring-primary' : 'opacity-70'}`} />
                  ))}
                </div>
              )}
            </div>
          )}
          {media?.capabilities?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {media.capabilities.map((c: string) => <Badge key={c} variant="outline" className="text-[0.65rem]">{c}</Badge>)}
            </div>
          )}
          {media?.trailer && <a href={media.trailer} target="_blank" rel="noopener noreferrer" className="text-sm text-primary inline-flex items-center gap-1"><ExternalLink className="h-3.5 w-3.5" /> Ver tráiler</a>}
        </Card>
      )}

      {/* Comparación mundial de precios */}
      <Card className="p-4">
        <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
          <h2 className="font-semibold flex items-center gap-2"><Globe className="h-4 w-4" /> Comparación mundial de precios</h2>
          <div className="flex items-center gap-2">
            <select value={cur} onChange={(e) => setCur(e.target.value)} className="border border-border rounded-md bg-background px-2 py-1 text-sm" title="Moneda de referencia">
              {CURRENCIES.filter((c) => c === 'USD' || rates[c]).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            {!live && (
              <Button size="sm" variant="outline" onClick={loadLive} disabled={liveLoading}>
                {liveLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Cargar 242 países en vivo</>}
              </Button>
            )}
          </div>
        </div>
        {liveErr && <div className="text-sm text-amber-600 dark:text-amber-500 mb-2">{liveErr} (la consulta en vivo puede fallar en local por el proxy TLS; anda en producción)</div>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground border-b">
                <th className="py-1.5 pr-2">#</th>
                <th className="py-1.5 pr-2">País</th>
                <th className="py-1.5 pr-2 text-right">Precio local</th>
                <th className="py-1.5 pr-2 text-right">{cur}</th>
                <th className="py-1.5 pr-2 text-right">Desc.</th>
                <th className="py-1.5 pr-2 text-right">Ahorro vs US</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: any, i: number) => {
                const save = usUsd && Number(r.price_usd) >= 0 ? Math.round((1 - Number(r.price_usd) / usUsd) * 100) : 0;
                return (
                  <tr key={r.market} className={`border-b border-border/50 ${i === 0 ? 'bg-green-600/5' : ''}`}>
                    <td className="py-1.5 pr-2 text-muted-foreground">{i === 0 ? '🏆' : i + 1}</td>
                    <td className="py-1.5 pr-2 whitespace-nowrap">{flag(r.market)} {countryName(r.market)} <span className="text-muted-foreground">{r.market}</span></td>
                    <td className="py-1.5 pr-2 text-right tabular-nums text-muted-foreground">{r.currency} {Number(r.list_price).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                    <td className="py-1.5 pr-2 text-right tabular-nums font-medium">{fmtRef(r.price_usd)}</td>
                    <td className="py-1.5 pr-2 text-right">{r.discount_pct > 0 ? <Badge variant="destructive" className="text-[0.6rem]">-{r.discount_pct}%</Badge> : ''}</td>
                    <td className="py-1.5 pr-2 text-right text-green-600 dark:text-green-500">{save > 0 ? `${save}%` : ''}</td>
                  </tr>
                );
              })}
              {rows.length === 0 && <tr><td colSpan={6} className="py-4 text-center text-muted-foreground">Sin precios.</td></tr>}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          {live ? `${rows.length} países (consulta en vivo)` : `${rows.length} mercados guardados`}. Precios convertidos con tasas de cambio; verificá antes de comprar.
        </p>
      </Card>

      {/* Variantes / denominaciones */}
      {Array.isArray(p.variants) && p.variants.length > 0 && (
        <Card className="p-4">
          <h2 className="font-semibold mb-2">Variantes / denominaciones {p.variants_market ? `(${p.variants_market})` : ''}</h2>
          <div className="space-y-1">
            {p.variants.map((v: any) => (
              <div key={v.sku_id} className="flex items-center justify-between text-sm border-b border-border/50 py-1">
                <span className="truncate">{v.title}{v.duration ? ` · ${v.duration}` : ''}</span>
                <span className="tabular-nums">{v.currency} {v.list_price} {v.price_usd != null && <span className="text-muted-foreground">(${Number(v.price_usd).toFixed(2)})</span>}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* A los usuarios también les gusta esto */}
      {related.length > 0 && (
        <Card className="p-4">
          <h2 className="font-semibold mb-3">A los usuarios también les gusta esto</h2>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3">
            {related.map((r: any) => (
              <button key={r.product_id} onClick={() => open(r.product_id)} className="group text-left">
                {r.image_boxart
                  ? <img src={r.image_boxart} alt={r.title} loading="lazy" className="w-full aspect-square object-cover rounded-md bg-muted group-hover:opacity-90" />
                  : <div className="w-full aspect-square rounded-md bg-muted flex items-center justify-center font-bold text-muted-foreground">{(r.title || '?').slice(0, 1)}</div>}
                <div className="text-xs mt-1 line-clamp-2 group-hover:underline">{r.title}</div>
                {r.cheapest?.price_usd != null && <div className="text-[0.7rem] text-muted-foreground">desde ${Number(r.cheapest.price_usd).toFixed(2)} {flag(r.cheapest.market)}</div>}
              </button>
            ))}
          </div>
        </Card>
      )}

      {/* Reseñas */}
      {reviews?.ratingsSummary && (
        <Card className="p-4">
          <div className="flex items-center gap-3 mb-3">
            <h2 className="font-semibold">Opiniones</h2>
            <span className="inline-flex items-center gap-1 text-sm"><Star className="h-4 w-4 fill-yellow-400 text-yellow-400" /> {Number(reviews.ratingsSummary.averageRating).toFixed(1)} <span className="text-muted-foreground">({reviews.ratingsSummary.totalRatingsCount})</span></span>
          </div>
          <div className="space-y-3">
            {(reviews.reviews || []).slice(0, 8).map((rv: any) => (
              <div key={rv.reviewId} className="border-b border-border/50 pb-2">
                <div className="flex items-center gap-2 text-sm">
                  <span className="inline-flex items-center gap-0.5 text-yellow-500">{'★'.repeat(Math.round(rv.rating))}<span className="text-muted-foreground">{'★'.repeat(5 - Math.round(rv.rating))}</span></span>
                  <span className="font-medium">{rv.title}</span>
                  <span className="text-xs text-muted-foreground">· {rv.userName} · {String(rv.submittedDateTime || '').slice(0, 10)}</span>
                </div>
                <p className="text-sm text-muted-foreground mt-0.5 whitespace-pre-line">{rv.reviewText}</p>
              </div>
            ))}
            {(!reviews.reviews || reviews.reviews.length === 0) && <div className="text-sm text-muted-foreground">Sin reseñas.</div>}
          </div>
        </Card>
      )}

      {/* Historial de precios (pendiente) */}
      <Card className="p-4">
        <h2 className="font-semibold mb-1">Historial de precios</h2>
        <p className="text-sm text-muted-foreground">Próximamente: gráfico histórico por país (requiere la tabla <code>price_history</code>, roadmap #5).</p>
      </Card>
    </div>
  );
}
