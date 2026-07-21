import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Search, Loader2, Package } from 'lucide-react';

const ATLAS_API = (import.meta as any).env?.VITE_ATLAS_API || 'http://127.0.0.1:8000';

// Set curado: un mercado por moneda distinta (~48). Captura toda la variación de
// precio sin el timeout de consultar las 242.
const CURATED_MARKETS = [
  'US','DE','GB','AR','BR','MX','CL','CO','PE','UY','TR','RU','UA','PL','CZ','HU','RO','BG',
  'SE','NO','DK','CH','IS','IN','ID','TH','VN','MY','PH','SG','JP','KR','TW','HK','CN','AU',
  'NZ','CA','ZA','NG','EG','KE','SA','AE','QA','KW','IL','KZ'
].join(',');

const flag = (c: string) =>
  c && c.length === 2
    ? String.fromCodePoint(...[...c.toUpperCase()].map((ch) => 127397 + ch.charCodeAt(0)))
    : '';

// Compara variantes/denominaciones (gift cards, packs de monedas, ediciones,
// duraciones de subs) de un producto en las 242 regiones, en vivo.
export function VariantExplorer() {
  const [productId, setProductId] = useState('CFQ7TTC0K8RT');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);
  const [selectedSku, setSelectedSku] = useState<string>('');

  const search = async () => {
    const id = productId.trim();
    if (!id) return;
    setLoading(true); setData(null); setSelectedSku('');
    try {
      const d = await fetch(`${ATLAS_API}/api/live/product/${id}?markets=${CURATED_MARKETS}`).then((r) => r.json());
      setData(d);
      const first = (d.variants || [])[0];
      if (first) setSelectedSku(first.sku_id);
    } catch {
      setData({ error: true });
    }
    setLoading(false);
  };

  const variants: any[] = data?.variants || [];
  // denominaciones distintas (sku_id -> título)
  const skus = Array.from(new Map(variants.map((v) => [v.sku_id, v.title])).entries());
  const rows = variants
    .filter((v) => v.sku_id === selectedSku)
    .sort((a, b) => (a.price_usd ?? 1e12) - (b.price_usd ?? 1e12));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" /> Variantes y denominaciones por región
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              placeholder="Product ID (ej. CFQ7TTC0K8RT gift card, o un Game Pass)"
              onKeyDown={(e) => e.key === 'Enter' && search()}
            />
            <Button onClick={search} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Search className="h-4 w-4 mr-2" />}
              Consultar
            </Button>
          </div>
          {loading && (
            <p className="text-sm text-muted-foreground mt-3">
              Consultando ~48 mercados en vivo… (~10s)
            </p>
          )}
          {data?.title && <p className="mt-3 font-medium">{data.title}</p>}
          {data && !loading && skus.length === 0 && !data.error && (
            <p className="text-sm text-muted-foreground mt-3">
              Este producto no devolvió variantes comprables.
            </p>
          )}
        </CardContent>
      </Card>

      {skus.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Elegí una denominación / variante</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {skus.map(([sku, title]) => (
                <Button
                  key={sku as string}
                  variant={sku === selectedSku ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSelectedSku(sku as string)}
                >
                  {String(title)}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {rows.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Precio por región ({rows.length}) — más barato arriba</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-h-[60vh] overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Región</TableHead>
                    <TableHead className="text-right">Precio local</TableHead>
                    <TableHead className="text-right">USD</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((v) => (
                    <TableRow key={v.market}>
                      <TableCell>
                        <span className="mr-1">{flag(v.market)}</span> {v.market}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {v.currency} {v.list_price}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {v.price_usd != null ? `$${Number(v.price_usd).toFixed(2)}` : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
