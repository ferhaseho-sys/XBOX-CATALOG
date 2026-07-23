/**
 * Panel de administración. Interno: no forma parte del sitio público.
 *
 * Responde dos preguntas sin entrar a la DB a mano:
 *   1. ¿Están frescos los datos y qué está roto?  (alertas + antigüedad por fase)
 *   2. ¿Cómo disparo una ingesta?                 (trabajos, uno a la vez)
 */
import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  AlertTriangle, CheckCircle2, Info, Play, RefreshCw, XCircle, Loader2,
} from 'lucide-react';
import { adminToken } from '../lib/admin';

const API = (import.meta as any).env?.VITE_ATLAS_API || 'http://127.0.0.1:8000';

type Alert = { level: 'error' | 'warn' | 'info'; msg: string };
type Run = {
  phase: string; market: string | null; status: string; n_products: number;
  finished_at: string | null; hours_ago: number | null; duration_s: number | null;
};
type Job = { name: string; label: string; duration: string };
type Current = {
  running: boolean; name: string | null; phase: string; detail: string;
  started_at: number | null; error: string | null;
};
type Status = {
  counts: Record<string, number>; markets_with_prices: number;
  runs: Run[]; alerts: Alert[]; job: Current;
};

const api = (path: string, init?: RequestInit) =>
  fetch(`${API}${path}`, { ...init, headers: { 'X-Admin-Token': adminToken() } });

/** "hace 3 h" / "hace 8,7 días": la antigüedad se lee mejor que un timestamp. */
function edad(horas: number | null): string {
  if (horas === null) return '—';
  if (horas < 1) return 'hace minutos';
  if (horas < 48) return `hace ${Math.round(horas)} h`;
  return `hace ${(horas / 24).toFixed(1)} días`;
}

function duracion(seg: number | null): string {
  if (seg === null) return '—';
  if (seg === 0) return 'sin medir';
  if (seg < 60) return `${seg} s`;
  if (seg < 3600) return `${Math.round(seg / 60)} min`;
  return `${(seg / 3600).toFixed(1)} h`;
}

const ICONO = { error: XCircle, warn: AlertTriangle, info: Info } as const;
const COLOR = {
  error: 'text-destructive',
  warn: 'text-amber-500',
  info: 'text-muted-foreground',
} as const;

export function AdminPanel() {
  const [st, setSt] = useState<Status | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [err, setErr] = useState('');
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    try {
      const [s, j] = await Promise.all([
        api('/api/admin/status').then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
        api('/api/admin/jobs').then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
      ]);
      setSt(s);
      setJobs(j.available);
      setErr('');
    } catch (e) {
      setErr(e === 401 || e === 503
        ? 'Sin permisos de administrador. Revisá el token.'
        : 'No se pudo hablar con la API.');
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  // mientras hay un trabajo corriendo se refresca solo; si no, se queda quieto
  useEffect(() => {
    if (!st?.job?.running) return;
    const t = setInterval(cargar, 4000);
    return () => clearInterval(t);
  }, [st?.job?.running, cargar]);

  const lanzar = async (name: string) => {
    const r = await api(`/api/admin/jobs/${name}`, { method: 'POST' });
    if (r.status === 409) setErr('Ya hay un trabajo corriendo.');
    await cargar();
  };

  if (cargando) {
    return <div className="flex items-center gap-2 text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" /> Cargando estado del sistema…
    </div>;
  }
  if (err && !st) return <div className="text-destructive">{err}</div>;
  if (!st) return null;

  const corriendo = st.job?.running;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Panel de administración</h2>
          <p className="text-xs text-muted-foreground">
            Estado del sistema y ejecución de ingestas. No visible para el público.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={cargar}>
          <RefreshCw className="h-4 w-4 mr-2" /> Actualizar
        </Button>
      </div>

      {err && <div className="text-sm text-destructive">{err}</div>}

      {/* Alertas: lo primero que hay que ver es qué está mal */}
      <Card>
        <CardHeader><CardTitle className="text-base">Diagnóstico</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {st.alerts.length === 0 ? (
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              Todo al día.
            </div>
          ) : st.alerts.map((a, i) => {
            const Icon = ICONO[a.level];
            return (
              <div key={i} className="flex items-start gap-2 text-sm">
                <Icon className={`h-4 w-4 mt-0.5 flex-shrink-0 ${COLOR[a.level]}`} />
                <span>{a.msg}</span>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Volumen de datos */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          ['Productos', st.counts.products],
          ['Precios', st.counts.prices],
          ['Market catalog', st.counts.market_catalog],
          ['Ofertas', st.counts.deals],
          ['Variantes', st.counts.variants],
          ['Mercados', st.markets_with_prices],
        ].map(([label, n]) => (
          <Card key={label as string}>
            <CardContent className="p-4">
              <div className="text-xs text-muted-foreground">{label}</div>
              <div className="text-xl font-semibold tabular-nums">
                {typeof n === 'number' ? n.toLocaleString('es-AR') : '—'}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <p className="text-xs text-muted-foreground -mt-3">
        Los conteos de tablas grandes son estimaciones de Postgres (evitan recorrerlas enteras).
      </p>

      {/* Frescura por fase */}
      <Card>
        <CardHeader><CardTitle className="text-base">Última corrida por fase</CardTitle></CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr className="text-left border-b">
                  <th className="py-2 pr-4">Fase</th>
                  <th className="py-2 pr-4">Antigüedad</th>
                  <th className="py-2 pr-4">Duración</th>
                  <th className="py-2 pr-4 text-right">Registros</th>
                </tr>
              </thead>
              <tbody>
                {st.runs.map((r) => (
                  <tr key={r.phase} className="border-b last:border-0">
                    <td className="py-2 pr-4 font-medium">{r.phase}</td>
                    <td className="py-2 pr-4">{edad(r.hours_ago)}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{duracion(r.duration_s)}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {r.n_products?.toLocaleString('es-AR') ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Trabajos */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            Ingestas
            {corriendo && (
              <Badge variant="default">
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                {st.job.name}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {st.job?.error && (
            <div className="text-sm text-destructive">Último error: {st.job.error}</div>
          )}
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {jobs.map((j) => (
              <div key={j.name}
                   className="flex items-center justify-between gap-3 rounded-md border p-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{j.label}</div>
                  <div className="text-xs text-muted-foreground">{j.duration}</div>
                </div>
                <Button size="sm" variant="outline" disabled={corriendo}
                        onClick={() => lanzar(j.name)}>
                  <Play className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Un trabajo por vez: todos son pesados y comparten la misma base.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
