import React, { useCallback, useEffect, useState } from 'react';
import { Activity, CalendarDays, CheckCircle2, Clock3, RefreshCw, Users } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';

const toList = (value) => Array.isArray(value) ? value : (value?.items || value?.data || []);
const display = (value) => value === null || value === undefined || value === '' ? '—' : String(value).replaceAll('_', ' ');

/** Reusable enterprise list/dashboard shell used by Workforce Core pages. */
export default function WorkforceWorkspace({ title, subtitle, icon: Icon = Activity, load, columns = [], metrics }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try { setData((await load()).data); }
    catch (err) { setError(err.response?.data?.detail || 'Workforce data could not be loaded.'); }
    finally { setLoading(false); }
  }, [load]);

  useEffect(() => { refresh(); }, [refresh]);
  const rows = toList(data);
  const cards = metrics ? metrics(data, rows) : [
    { label: 'Records', value: rows.length, icon: Users },
    { label: 'Status', value: loading ? 'Syncing' : 'Current', icon: CheckCircle2 },
  ];

  return <div className="space-y-6">
    <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4"><div className="rounded-xl bg-indigo-500/15 p-3"><Icon className="h-7 w-7 text-indigo-300" /></div><div><h1 className="text-2xl font-bold text-white">{title}</h1><p className="mt-1 text-sm text-gray-400">{subtitle}</p></div></div>
        <Button variant="secondary" onClick={refresh} isLoading={loading}><RefreshCw className="h-4 w-4" />Refresh</Button>
      </div>
    </section>
    {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}
    <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{cards.map(({ label, value, icon: MetricIcon = Clock3 }) => <Card key={label} className="p-5"><div className="flex items-center justify-between"><div><p className="text-xs font-medium uppercase tracking-wider text-gray-500">{label}</p><p className="mt-2 text-2xl font-bold text-white">{display(value)}</p></div><MetricIcon className="h-5 w-5 text-indigo-400" /></div></Card>)}</section>
    <Card className="overflow-hidden p-0"><CardHeader className="border-b border-gray-800 px-6 py-5"><CardTitle>{title} records</CardTitle></CardHeader><CardContent className="overflow-x-auto p-0">
      {loading ? <div className="p-10 text-center text-sm text-gray-400">Loading workforce data…</div> : rows.length === 0 ? <div className="p-10 text-center text-sm text-gray-400">No records are available for this tenant yet.</div> : <table className="min-w-full text-left text-sm"><thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500"><tr>{columns.map((col) => <th key={col.key} className="px-6 py-3 font-medium">{col.label}</th>)}</tr></thead><tbody className="divide-y divide-gray-800">{rows.map((row, index) => <tr key={row.id ?? index} className="hover:bg-gray-800/40">{columns.map((col) => <td key={col.key} className="whitespace-nowrap px-6 py-4 text-gray-300">{col.badge ? <Badge variant="primary">{display(row[col.key])}</Badge> : display(col.format ? col.format(row) : row[col.key])}</td>)}</tr>)}</tbody></table>}
    </CardContent></Card>
  </div>;
}
