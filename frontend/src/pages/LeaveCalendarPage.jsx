import React, { useState, useEffect, useCallback } from 'react';
import {
  Calendar, RefreshCw, ChevronLeft, ChevronRight, User, Loader2
} from 'lucide-react';
import { leaveService } from '../services/leaveService';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { useAuthStore } from '../store/authStore';
import { usePermission } from '../hooks/usePermission';

// The API returns lowercase statuses; normalise on the way in so these
// uppercase-keyed maps stay correct. Comparing raw values against uppercase
// literals silently matched nothing, leaving the calendar empty.
const normalizeStatus = (value) => String(value ?? '').toUpperCase();

const STATUS_COLORS = {
  PENDING: '#f59e0b',
  APPROVED: '#22c55e',
  REJECTED: '#ef4444',
  CANCELLED: '#64748b',
};

const LEAVE_TYPE_COLORS = [
  '#6366f1', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7',
  '#14b8a6', '#f97316', '#ec4899', '#06b6d4',
];

function MonthCalendar({ year, month, requests }) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();

  const requestsByDay = {};
  requests.forEach(r => {
    if (normalizeStatus(r.status) !== 'APPROVED') return;
    const start = new Date(r.start_date);
    const end = new Date(r.end_date);
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      if (d.getFullYear() === year && d.getMonth() === month) {
        const key = d.getDate();
        if (!requestsByDay[key]) requestsByDay[key] = [];
        requestsByDay[key].push(r);
      }
    }
  });

  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  return (
    <div>
      <div className="grid grid-cols-7 mb-2">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
          <div key={d} className="py-2 text-center text-xs font-semibold text-gray-500">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, i) => {
          if (!day) return <div key={i} />;
          const isToday = today.getFullYear() === year && today.getMonth() === month && today.getDate() === day;
          const dayRequests = requestsByDay[day] || [];
          return (
            <div key={day} className={`min-h-[72px] rounded-xl p-1.5 border transition-colors ${
              isToday ? 'border-indigo-500/50 bg-indigo-500/10' : 'border-gray-800 bg-gray-900/50 hover:bg-gray-800/50'
            }`}>
              <span className={`text-xs font-semibold ${isToday ? 'text-indigo-300' : 'text-gray-400'}`}>{day}</span>
              <div className="mt-1 space-y-0.5">
                {dayRequests.slice(0, 3).map((r) => (
                  <div key={r.id} className="truncate rounded px-1 py-0.5 text-xs font-medium"
                    style={{ background: `${LEAVE_TYPE_COLORS[r.leave_type_id % LEAVE_TYPE_COLORS.length]}22`, color: LEAVE_TYPE_COLORS[r.leave_type_id % LEAVE_TYPE_COLORS.length] }}>
                    #{r.user_id}
                  </div>
                ))}
                {dayRequests.length > 3 && (
                  <div className="text-xs text-gray-600 pl-1">+{dayRequests.length - 3} more</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function LeaveCalendarPage() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth());
  const { user } = useAuthStore();
  const { hasPermission } = usePermission();

  const canViewTeam = hasPermission('leave.view_team');
  const canViewOrg = hasPermission('leave.view_org');

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const res = await leaveService.getRequests({ limit: 500 });
      setRequests(Array.isArray(res.data) ? res.data : (res.data?.items || []));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load leave calendar');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const prevMonth = () => {
    if (month === 0) { setMonth(11); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (month === 11) { setMonth(0); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  };

  const monthName = new Date(year, month).toLocaleString('default', { month: 'long', year: 'numeric' });

  // Filter requests based on user permissions
  const visibleRequests = requests.filter(r => {
    // Always allow viewing own requests
    if (r.user_id === user?.id) return true;
    // Allow viewing team requests if user has leave.view_team permission
    if (canViewTeam && r.dept_id && r.dept_id === user?.dept_id) return true;
    // Allow viewing all org requests if user has leave.view_org permission
    if (canViewOrg) return true;
    return false;
  });

  const monthRequests = visibleRequests.filter(r => {
    const start = new Date(r.start_date);
    const end = new Date(r.end_date);
    const monthStart = new Date(year, month, 1);
    const monthEnd = new Date(year, month + 1, 0);
    return start <= monthEnd && end >= monthStart;
  });

  const statusSummary = visibleRequests.reduce((acc, r) => {
    acc[r.status] = (acc[r.status] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-indigo-500/15 p-3">
              <Calendar className="h-7 w-7 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Leave Calendar</h1>
              <p className="mt-1 text-sm text-gray-400">Visual overview of approved leaves across the organization</p>
            </div>
          </div>
          <Button variant="secondary" onClick={refresh} isLoading={loading}>
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        </div>
      </section>

      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {/* Summary KPIs */}
      <div className="grid grid-cols-4 gap-4">
        {Object.entries({ PENDING: 'Pending', APPROVED: 'Approved', REJECTED: 'Rejected', CANCELLED: 'Cancelled' }).map(([k, label]) => (
          <Card key={k} className="p-5">
            <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">{label}</p>
            <p className="text-3xl font-bold mt-2" style={{ color: STATUS_COLORS[k] || '#fff' }}>
              {statusSummary[k] || 0}
            </p>
          </Card>
        ))}
      </div>

      {/* Calendar */}
      <Card>
        <CardHeader className="border-b border-gray-800 px-6 py-5">
          <div className="flex items-center justify-between">
            <CardTitle>{monthName}</CardTitle>
            <div className="flex items-center gap-2">
              <button onClick={prevMonth} className="p-2 rounded-xl hover:bg-gray-800 text-gray-400 hover:text-white transition-colors">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button onClick={() => { setMonth(new Date().getMonth()); setYear(new Date().getFullYear()); }}
                className="px-3 py-1.5 rounded-lg bg-gray-800 text-xs text-gray-300 hover:text-white transition-colors">
                Today
              </button>
              <button onClick={nextMonth} className="p-2 rounded-xl hover:bg-gray-800 text-gray-400 hover:text-white transition-colors">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6">
          {loading ? (
            <div className="h-96 flex items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
            </div>
          ) : (
            <MonthCalendar year={year} month={month} requests={visibleRequests} />
          )}
        </CardContent>
      </Card>

      {/* Leave list for this month */}
      {monthRequests.length > 0 && (
        <Card className="overflow-hidden p-0">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Leave in {monthName} ({monthRequests.length})</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                <tr>
                  <th className="px-6 py-3">Employee</th>
                  <th className="px-6 py-3">Period</th>
                  <th className="px-6 py-3">Days</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {monthRequests.map(r => {
                  const days = Math.ceil((new Date(r.end_date) - new Date(r.start_date)) / 86400000) + 1;
                  return (
                    <tr key={r.id} className="hover:bg-gray-800/40 transition-colors">
                      <td className="px-6 py-4 font-medium text-white">
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4 text-gray-500" />
                          #{r.user_id}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-gray-300 text-xs font-mono">{r.start_date} → {r.end_date}</td>
                      <td className="px-6 py-4 text-gray-300">{days}d</td>
                      <td className="px-6 py-4">
                        <span className="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold"
                          style={{ background: `${STATUS_COLORS[r.status] || '#6366f1'}1a`, color: STATUS_COLORS[r.status] || '#6366f1' }}>
                          {r.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-gray-400 text-xs max-w-xs truncate">{r.reason || '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
