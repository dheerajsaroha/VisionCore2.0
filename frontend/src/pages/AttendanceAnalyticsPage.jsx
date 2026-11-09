import React, { useState, useEffect, useCallback } from 'react';
import { BarChart2, RefreshCw, Users, Activity, CheckCircle2, AlertTriangle } from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { workforceService } from '../services/workforceService';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';

const STATUS_COLORS = {
  PRESENT: '#22c55e', LATE: '#f59e0b', ABSENT: '#ef4444',
  HALF_DAY: '#a855f7', WFH: '#3b82f6', ON_LEAVE: '#6366f1',
  MISSED_PUNCH: '#f97316', HOLIDAY: '#14b8a6',
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl bg-gray-900 border border-gray-700 px-4 py-3 shadow-xl text-xs space-y-1">
      <p className="font-semibold text-gray-200 mb-1">{label}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: {p.value}{p.unit || ''}</p>
      ))}
    </div>
  );
};

function StatCard({ label, value, sub, color, icon: Icon }) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">{label}</p>
          <p className="mt-2 text-3xl font-bold text-white">{value ?? '—'}</p>
          {sub && <p className="mt-1 text-xs text-gray-500">{sub}</p>}
        </div>
        {Icon && (
          <div className="rounded-xl p-3" style={{ background: `${color}1a` }}>
            <Icon className="h-6 w-6" style={{ color }} />
          </div>
        )}
      </div>
    </Card>
  );
}

export default function AttendanceAnalyticsPage() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [days, setDays] = useState(30);

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const res = await workforceService.analytics.dashboard({ days });
      setAnalytics(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { refresh(); }, [refresh]);

  const a = analytics || {};
  const total = a.total_sessions || 0;
  const trends = (a.trends || []).slice(-Math.min(days, 30));

  const rateData = trends.map(t => ({
    date: t.date?.slice(5),
    present: t.present_rate ?? 0,
    late: t.late_rate ?? 0,
    absent: t.absent_rate ?? 0,
  }));

  const countData = trends.map(t => ({
    date: t.date?.slice(5),
    Present: t.present ?? 0,
    Late: t.late ?? 0,
    Absent: t.absent ?? 0,
  }));

  const pieData = [
    { name: 'Present', value: a.present_count || 0, color: STATUS_COLORS.PRESENT },
    { name: 'Late', value: a.late_count || 0, color: STATUS_COLORS.LATE },
    { name: 'Absent', value: a.absent_count || 0, color: STATUS_COLORS.ABSENT },
    { name: 'WFH', value: a.wfh_count || 0, color: STATUS_COLORS.WFH },
    { name: 'On Leave', value: a.on_leave_count || 0, color: STATUS_COLORS.ON_LEAVE },
    { name: 'Missed Punch', value: a.missed_punch_count || 0, color: STATUS_COLORS.MISSED_PUNCH },
    { name: 'Holiday', value: a.holiday_count || 0, color: STATUS_COLORS.HOLIDAY },
  ].filter(d => d.value > 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-indigo-500/15 p-3">
              <BarChart2 className="h-7 w-7 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Attendance Analytics</h1>
              <p className="mt-1 text-sm text-gray-400">Deep workforce attendance metrics, trends, and rate analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex rounded-xl overflow-hidden border border-gray-700">
              {[7, 30, 90].map(d => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${days === d ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}`}
                >
                  {d}d
                </button>
              ))}
            </div>
            <Button variant="secondary" onClick={refresh} isLoading={loading}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
          </div>
        </div>
      </section>

      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Present Rate" value={`${a.present_rate ?? 0}%`} sub={`${a.present_count ?? 0} sessions`} color="#22c55e" icon={CheckCircle2} />
        <StatCard label="Late Rate" value={`${a.late_rate ?? 0}%`} sub={`${a.late_count ?? 0} sessions`} color="#f59e0b" icon={AlertTriangle} />
        <StatCard label="Absent Rate" value={`${a.absent_rate ?? 0}%`} sub={`${a.absent_count ?? 0} sessions`} color="#ef4444" icon={Users} />
        <StatCard label="Total Sessions" value={total} sub={`Over ${days} days`} color="#6366f1" icon={Activity} />
      </div>

      {/* Rate Trend Chart */}
      <Card>
        <CardHeader className="border-b border-gray-800 px-6 py-5">
          <CardTitle>Attendance Rate Trends (%)</CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          {loading ? (
            <div className="h-64 flex items-center justify-center text-sm text-gray-500">Loading…</div>
          ) : rateData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-sm text-gray-500">No trend data available</div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={rateData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <defs>
                  {['present', 'late', 'absent'].map((key, i) => {
                    const colors = ['#22c55e', '#f59e0b', '#ef4444'];
                    return (
                      <linearGradient key={key} id={`grad_${key}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={colors[i]} stopOpacity={0.25} />
                        <stop offset="95%" stopColor={colors[i]} stopOpacity={0} />
                      </linearGradient>
                    );
                  })}
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#6b7280' }} />
                <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} domain={[0, 100]} unit="%" />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11, color: '#9ca3af' }} />
                <Area type="monotone" dataKey="present" name="Present %" stroke="#22c55e" fill="url(#grad_present)" strokeWidth={2} />
                <Area type="monotone" dataKey="late" name="Late %" stroke="#f59e0b" fill="url(#grad_late)" strokeWidth={2} />
                <Area type="monotone" dataKey="absent" name="Absent %" stroke="#ef4444" fill="url(#grad_absent)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Count Bar Chart + Pie */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Daily Session Counts</CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            {loading ? (
              <div className="h-56 flex items-center justify-center text-sm text-gray-500">Loading…</div>
            ) : countData.length === 0 ? (
              <div className="h-56 flex items-center justify-center text-sm text-gray-500">No data</div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={countData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#6b7280' }} />
                  <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 11, color: '#9ca3af' }} />
                  <Bar dataKey="Present" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Late" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Absent" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Status Breakdown</CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            {loading ? (
              <div className="h-56 flex items-center justify-center text-sm text-gray-500">Loading…</div>
            ) : pieData.length === 0 ? (
              <div className="h-56 flex items-center justify-center text-sm text-gray-500">No data</div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={140}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={35} outerRadius={60} dataKey="value" paddingAngle={2}>
                      {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                    </Pie>
                    <Tooltip formatter={(v) => [`${v} sessions`]} contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 12, fontSize: 11 }} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="mt-4 space-y-2">
                  {pieData.map(d => (
                    <div key={d.name} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: d.color }} />
                        <span className="text-gray-400">{d.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="h-1 w-16 rounded-full bg-gray-800">
                          <div className="h-1 rounded-full" style={{ background: d.color, width: `${Math.round(d.value / (total || 1) * 100)}%` }} />
                        </div>
                        <span className="font-semibold text-white w-8 text-right">{d.value}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
