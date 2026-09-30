import React, { useState, useEffect, useCallback } from 'react';
import {
  CheckCircle2, Clock, AlertTriangle, Users, RefreshCw,
  Calendar, Wifi, Smartphone, Monitor, MapPin, Plus, X,
  TrendingUp, TrendingDown, Activity
  , FileEdit
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { workforceService } from '../services/workforceService';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { usePermission } from '../hooks/usePermission';
import { useToast } from '../components/ui/Toast';

const CHANNEL_ICONS = {
  FACE: <Users className="h-3 w-3" />,
  QR: <Smartphone className="h-3 w-3" />,
  GPS: <MapPin className="h-3 w-3" />,
  KIOSK: <Monitor className="h-3 w-3" />,
  WiFi: <Wifi className="h-3 w-3" />,
  MANUAL: <Activity className="h-3 w-3" />,
};

const STATUS_COLORS = {
  PRESENT: '#22c55e',
  LATE: '#f59e0b',
  ABSENT: '#ef4444',
  HALF_DAY: '#a855f7',
  WFH: '#3b82f6',
  ON_LEAVE: '#6366f1',
  HOLIDAY: '#14b8a6',
  WEEKEND: '#64748b',
  MISSED_PUNCH: '#f97316',
};

const STATUS_VARIANTS = {
  PRESENT: 'success',
  LATE: 'warning',
  ABSENT: 'danger',
  HALF_DAY: 'primary',
  WFH: 'primary',
  ON_LEAVE: 'secondary',
  HOLIDAY: 'secondary',
  WEEKEND: 'secondary',
  MISSED_PUNCH: 'warning',
};

const CHANNELS = ['FACE', 'QR', 'GPS', 'BLE', 'NFC', 'WiFi', 'KIOSK', 'MANUAL'];

function KPICard({ label, value, icon: Icon, color, sub, trend }) {
  return (
    <Card className="relative overflow-hidden">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">{label}</p>
            <p className="mt-2 text-3xl font-bold text-white">{value ?? '—'}</p>
            {sub && <p className="mt-1 text-xs text-gray-500">{sub}</p>}
          </div>
          <div className={`rounded-xl p-3`} style={{ background: `${color}1a` }}>
            <Icon className="h-6 w-6" style={{ color }} />
          </div>
        </div>
        {trend !== undefined && (
          <div className={`mt-3 flex items-center gap-1 text-xs font-medium ${trend >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {trend >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {Math.abs(trend)}% vs last period
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MarkAttendanceModal({ isOpen, onClose, onSuccess }) {
  const [form, setForm] = useState({ user_id: '', channel: 'FACE', check_in: '', check_out: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const payload = {
        user_id: parseInt(form.user_id),
        channel: form.channel,
        check_in: form.check_in ? new Date(form.check_in).toISOString() : undefined,
        check_out: form.check_out ? new Date(form.check_out).toISOString() : undefined,
      };
      await workforceService.attendance.mark(payload);
      onSuccess();
      onClose();
      setForm({ user_id: '', channel: 'FACE', check_in: '', check_out: '' });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to mark attendance');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Mark Attendance">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">{error}</div>}
        <Input
          label="User ID"
          type="number"
          value={form.user_id}
          onChange={(e) => setForm(f => ({ ...f, user_id: e.target.value }))}
          required
          placeholder="Employee user ID"
        />
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">Channel</label>
          <select
            value={form.channel}
            onChange={(e) => setForm(f => ({ ...f, channel: e.target.value }))}
            className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {CHANNELS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <Input
          label="Check-In Time"
          type="datetime-local"
          value={form.check_in}
          onChange={(e) => setForm(f => ({ ...f, check_in: e.target.value }))}
        />
        <Input
          label="Check-Out Time"
          type="datetime-local"
          value={form.check_out}
          onChange={(e) => setForm(f => ({ ...f, check_out: e.target.value }))}
        />
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={loading}>Record Attendance</Button>
        </div>
      </form>
    </Modal>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl bg-gray-900 border border-gray-700 px-4 py-3 shadow-xl text-xs space-y-1">
      <p className="font-semibold text-gray-200">{label}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: {p.value}</p>
      ))}
    </div>
  );
};

export default function AttendanceDashboardPage() {
  const [analytics, setAnalytics] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [markOpen, setMarkOpen] = useState(false);
  const [days, setDays] = useState(30);
  const [statusFilter, setStatusFilter] = useState('');
  const [pendingCorrections, setPendingCorrections] = useState([]);
  const [reviewRequest, setReviewRequest] = useState(null);
  const [reviewNote, setReviewNote] = useState('');
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const { hasPermission } = usePermission();
  const toast = useToast();
  const canReviewCorrections = hasPermission('attendance_correction:approve');

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [analyticsRes, sessionsRes, correctionsRes] = await Promise.all([
        workforceService.analytics.dashboard({ days }),
        workforceService.attendance.sessions({ status: statusFilter || undefined, limit: 50 }),
        canReviewCorrections
          ? workforceService.corrections.listPending()
          : Promise.resolve({ data: { requests: [] } }),
      ]);
      setAnalytics(analyticsRes.data);
      setSessions(Array.isArray(sessionsRes.data) ? sessionsRes.data : []);
      setPendingCorrections(correctionsRes.data?.requests || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load attendance data');
    } finally {
      setLoading(false);
    }
  }, [days, statusFilter, canReviewCorrections]);

  useEffect(() => { refresh(); }, [refresh]);

  const a = analytics || {};
  const total = a.total_sessions || 0;

  const pieData = [
    { name: 'Present', value: a.present_count || 0, color: STATUS_COLORS.PRESENT },
    { name: 'Late', value: a.late_count || 0, color: STATUS_COLORS.LATE },
    { name: 'Absent', value: a.absent_count || 0, color: STATUS_COLORS.ABSENT },
    { name: 'WFH', value: a.wfh_count || 0, color: STATUS_COLORS.WFH },
    { name: 'On Leave', value: a.on_leave_count || 0, color: STATUS_COLORS.ON_LEAVE },
    { name: 'Missed Punch', value: a.missed_punch_count || 0, color: STATUS_COLORS.MISSED_PUNCH },
  ].filter(d => d.value > 0);

  const trends = (a.trends || []).slice(-14);

  const reviewCorrection = async (action) => {
    if (!reviewRequest) return;
    if (action === 'reject' && !reviewNote.trim()) {
      setReviewError('A rejection reason is required.');
      return;
    }
    setReviewLoading(true);
    setReviewError('');
    try {
      if (action === 'approve') {
        await workforceService.corrections.approve(reviewRequest.id, reviewNote.trim());
      } else {
        await workforceService.corrections.reject(reviewRequest.id, reviewNote.trim());
      }
      toast({ message: `Correction request ${action}d.`, type: 'success' });
      setReviewRequest(null);
      setReviewNote('');
      await refresh();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setReviewError(typeof detail === 'string' ? detail : detail?.message || 'Unable to review correction request.');
    } finally {
      setReviewLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-indigo-500/15 p-3">
              <Activity className="h-7 w-7 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Attendance Dashboard</h1>
              <p className="mt-1 text-sm text-gray-400">Live multi-channel attendance health across your organization</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={days}
              onChange={e => setDays(Number(e.target.value))}
              className="rounded-xl bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
            <Button variant="secondary" onClick={refresh} isLoading={loading}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button onClick={() => setMarkOpen(true)}>
              <Plus className="h-4 w-4" /> Mark Attendance
            </Button>
          </div>
        </div>
      </section>

      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        <KPICard label="Total Sessions" value={total} icon={Calendar} color="#6366f1" />
        <KPICard label="Present" value={a.present_count} sub={`${a.present_rate ?? 0}% rate`} icon={CheckCircle2} color="#22c55e" />
        <KPICard label="Late" value={a.late_count} sub={`${a.late_rate ?? 0}% rate`} icon={AlertTriangle} color="#f59e0b" />
        <KPICard label="Absent" value={a.absent_count} sub={`${a.absent_rate ?? 0}% rate`} icon={X} color="#ef4444" />
        <KPICard label="WFH" value={a.wfh_count} icon={Monitor} color="#3b82f6" />
        <KPICard label="On Leave" value={a.on_leave_count} icon={Clock} color="#a855f7" />
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Trend Area Chart */}
        <Card className="lg:col-span-2">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Attendance Trend ({days}d)</CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            {loading ? (
              <div className="h-56 flex items-center justify-center text-sm text-gray-500">Loading…</div>
            ) : trends.length === 0 ? (
              <div className="h-56 flex items-center justify-center text-sm text-gray-500">No trend data available</div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={trends} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="presentGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="lateGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="absentGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={v => v?.slice(5)} />
                  <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 11, color: '#9ca3af' }} />
                  <Area type="monotone" dataKey="present" name="Present" stroke="#22c55e" fill="url(#presentGrad)" strokeWidth={2} />
                  <Area type="monotone" dataKey="late" name="Late" stroke="#f59e0b" fill="url(#lateGrad)" strokeWidth={2} />
                  <Area type="monotone" dataKey="absent" name="Absent" stroke="#ef4444" fill="url(#absentGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Status Distribution Pie */}
        <Card>
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Status Distribution</CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            {loading ? (
              <div className="h-56 flex items-center justify-center text-sm text-gray-500">Loading…</div>
            ) : pieData.length === 0 ? (
              <div className="h-56 flex items-center justify-center text-sm text-gray-500">No data</div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={160}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} dataKey="value" paddingAngle={2}>
                      {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                    </Pie>
                    <Tooltip formatter={(v, n) => [`${v} sessions`, n]} contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 12, fontSize: 11 }} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="mt-3 space-y-1.5">
                  {pieData.map(d => (
                    <div key={d.name} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: d.color }} />
                        <span className="text-gray-400">{d.name}</span>
                      </div>
                      <span className="font-semibold text-white">{d.value}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Session Table */}
      {canReviewCorrections && (
        <Card className="overflow-hidden p-0">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <div className="flex items-center justify-between">
              <CardTitle>Pending Correction Requests</CardTitle>
              <Badge variant={pendingCorrections.length ? 'warning' : 'default'}>
                {pendingCorrections.length} pending
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            {pendingCorrections.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-500">No pending correction requests.</div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-6 py-3 font-medium">Employee</th>
                    <th className="px-6 py-3 font-medium">Attendance log</th>
                    <th className="px-6 py-3 font-medium">Requested values</th>
                    <th className="px-6 py-3 font-medium">Submitted</th>
                    <th className="px-6 py-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {pendingCorrections.map((request) => (
                    <tr key={request.id}>
                      <td className="px-6 py-4 text-white">Employee #{request.employee_user_id}</td>
                      <td className="px-6 py-4 text-gray-300">{request.attendance_log_id ?? 'Missing log'}</td>
                      <td className="px-6 py-4 text-xs text-gray-400">
                        {request.request_payload?.requested_clock_in || '—'}
                        {' → '}
                        {request.request_payload?.requested_clock_out || '—'}
                        <p className="mt-1 text-gray-500">{request.request_payload?.reason || 'No reason supplied'}</p>
                      </td>
                      <td className="px-6 py-4 text-xs text-gray-400">{request.submitted_at ? new Date(request.submitted_at).toLocaleString() : '—'}</td>
                      <td className="px-6 py-4">
                        <Button type="button" variant="secondary" className="px-3 py-1.5 text-xs" onClick={() => { setReviewRequest(request); setReviewNote(''); setReviewError(''); }}>
                          <FileEdit className="h-3.5 w-3.5" /> Review
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      <Modal isOpen={!!reviewRequest} onClose={() => setReviewRequest(null)} title="Review Attendance Correction">
        <div className="space-y-4">
          {reviewError && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{reviewError}</div>}
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 text-sm text-gray-300">
            <p>Employee #{reviewRequest?.employee_user_id} · Log #{reviewRequest?.attendance_log_id ?? 'missing'}</p>
            <p className="mt-2 text-xs text-gray-400">Current attendance values are validated and applied by the server.</p>
            <p className="mt-2 text-xs text-gray-400">Requested: {reviewRequest?.request_payload?.requested_clock_in || '—'} → {reviewRequest?.request_payload?.requested_clock_out || '—'}</p>
            <p className="mt-2 text-xs text-gray-400">Reason: {reviewRequest?.request_payload?.reason || '—'}</p>
          </div>
          <Input label="Decision notes" value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="Optional for approval; required for rejection" />
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={() => setReviewRequest(null)}>Cancel</Button>
            <Button type="button" variant="danger" isLoading={reviewLoading} onClick={() => reviewCorrection('reject')}>Reject</Button>
            <Button type="button" isLoading={reviewLoading} onClick={() => reviewCorrection('approve')}>Approve</Button>
          </div>
        </div>
      </Modal>

      <Card className="overflow-hidden p-0">
        <CardHeader className="border-b border-gray-800 px-6 py-5">
          <div className="flex items-center justify-between">
            <CardTitle>Recent Sessions</CardTitle>
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="rounded-xl bg-gray-800 border border-gray-700 px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">All Statuses</option>
              {Object.keys(STATUS_COLORS).map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {loading ? (
            <div className="p-10 text-center text-sm text-gray-500">Loading sessions…</div>
          ) : sessions.length === 0 ? (
            <div className="p-10 text-center text-sm text-gray-500">No attendance sessions found for this period.</div>
          ) : (
            <table className="min-w-full text-left text-sm">
              <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                <tr>
                  <th className="px-6 py-3 font-medium">User</th>
                  <th className="px-6 py-3 font-medium">Date</th>
                  <th className="px-6 py-3 font-medium">Channel</th>
                  <th className="px-6 py-3 font-medium">Check In</th>
                  <th className="px-6 py-3 font-medium">Check Out</th>
                  <th className="px-6 py-3 font-medium">Hours</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {sessions.map(s => (
                  <tr key={s.id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="px-6 py-4 font-medium text-white">#{s.user_id}</td>
                    <td className="px-6 py-4 text-gray-300">{s.work_date}</td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-500/10 px-2.5 py-1 text-xs font-medium text-indigo-300">
                        {CHANNEL_ICONS[s.channel] || <Activity className="h-3 w-3" />}
                        {s.channel}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-300 font-mono text-xs">
                      {s.check_in ? new Date(s.check_in).toLocaleTimeString() : '—'}
                    </td>
                    <td className="px-6 py-4 text-gray-300 font-mono text-xs">
                      {s.check_out ? new Date(s.check_out).toLocaleTimeString() : '—'}
                    </td>
                    <td className="px-6 py-4 text-gray-300">
                      {s.work_hours != null ? `${s.work_hours}h` : '—'}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold`}
                        style={{ background: `${STATUS_COLORS[s.status] || '#6366f1'}1a`, color: STATUS_COLORS[s.status] || '#6366f1' }}>
                        {s.status?.replace('_', ' ')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <MarkAttendanceModal isOpen={markOpen} onClose={() => setMarkOpen(false)} onSuccess={refresh} />
    </div>
  );
}
