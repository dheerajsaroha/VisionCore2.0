import React, { useState, useEffect, useCallback } from 'react';
import { Clock, ChevronRight, User, CheckCircle2, AlertTriangle, Activity, RefreshCw, Calendar } from 'lucide-react';
import { workforceService } from '../services/workforceService';
import { Button } from '../components/ui/Button';
import { Card, CardContent } from '../components/ui/Card';
import '../components/ui/Input';

const STATUS_COLORS = {
  PRESENT: '#22c55e', LATE: '#f59e0b', ABSENT: '#ef4444',
  HALF_DAY: '#a855f7', WFH: '#3b82f6', ON_LEAVE: '#6366f1',
  HOLIDAY: '#14b8a6', WEEKEND: '#64748b', MISSED_PUNCH: '#f97316',
};

const EVENT_COLORS = { IN: '#22c55e', OUT: '#ef4444', BREAK_START: '#f59e0b', BREAK_END: '#3b82f6' };

function TimelineDot({ type }) {
  return (
    <div className="flex items-center justify-center w-8 h-8 rounded-full border-2"
      style={{ borderColor: EVENT_COLORS[type] || '#6366f1', background: `${EVENT_COLORS[type] || '#6366f1'}1a` }}>
      <span className="text-xs font-bold" style={{ color: EVENT_COLORS[type] }}>
        {type === 'IN' ? '▶' : type === 'OUT' ? '■' : type === 'BREAK_START' ? '⏸' : '▷'}
      </span>
    </div>
  );
}

function SessionCard({ session, expanded, onToggle }) {
  const [events, setEvents] = useState([]);
  const [loadingEvents, setLoadingEvents] = useState(false);

  const loadEvents = useCallback(async () => {
    if (!expanded || events.length > 0) return;
    setLoadingEvents(true);
    try {
      const res = await workforceService.attendance.events(session.id);
      setEvents(Array.isArray(res.data) ? res.data : []);
    } catch { /* silent */ }
    finally { setLoadingEvents(false); }
  }, [expanded, session.id, events.length]);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  const color = STATUS_COLORS[session.status] || '#6366f1';
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-800/30 transition-colors"
      >
        <div className="flex items-center gap-4">
          <div className="w-3 h-3 rounded-full" style={{ background: color }} />
          <div className="text-left">
            <p className="text-sm font-semibold text-white">{session.work_date}</p>
            <p className="text-xs text-gray-400">
              {session.check_in ? new Date(session.check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'No check-in'}
              {' → '}
              {session.check_out ? new Date(session.check_out).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Active'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {session.work_hours != null && (
            <span className="text-xs font-medium text-gray-400">{session.work_hours}h</span>
          )}
          <span className="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold"
            style={{ background: `${color}1a`, color }}>
            {session.status?.replace('_', ' ')}
          </span>
          <span className="inline-flex items-center rounded-full bg-gray-800 px-2 py-1 text-xs text-gray-400">
            {session.channel}
          </span>
          <ChevronRight className={`h-4 w-4 text-gray-500 transition-transform ${expanded ? 'rotate-90' : ''}`} />
        </div>
      </button>
      {expanded && (
        <div className="px-5 pb-4 border-t border-gray-800">
          <p className="text-xs font-semibold text-gray-500 mt-3 mb-3 uppercase tracking-wider">Punch Events</p>
          {loadingEvents ? (
            <p className="text-xs text-gray-500">Loading events…</p>
          ) : events.length === 0 ? (
            <p className="text-xs text-gray-500">No punch events recorded for this session.</p>
          ) : (
            <div className="relative space-y-0">
              {events.map((ev, i) => (
                <div key={ev.id} className="flex items-start gap-4">
                  <div className="flex flex-col items-center">
                    <TimelineDot type={ev.event_type} />
                    {i < events.length - 1 && <div className="w-0.5 h-6 bg-gray-700 my-0.5" />}
                  </div>
                  <div className="pb-4">
                    <p className="text-sm font-medium text-white">{ev.event_type?.replace('_', ' ')}</p>
                    <p className="text-xs text-gray-500">
                      {new Date(ev.event_time).toLocaleString()} · {ev.channel}
                      {ev.gps_lat && ` · GPS: ${parseFloat(ev.gps_lat).toFixed(4)}, ${parseFloat(ev.gps_lng).toFixed(4)}`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function AttendanceTimelinePage() {
  const [userId, setUserId] = useState('');
  const [inputId, setInputId] = useState('');
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState({});
  const [limit, setLimit] = useState(30);

  const loadTimeline = useCallback(async () => {
    if (!userId) return;
    setLoading(true); setError('');
    try {
      const res = await workforceService.attendance.timeline(userId, { limit });
      setSessions(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load timeline');
    } finally {
      setLoading(false);
    }
  }, [userId, limit]);

  useEffect(() => { loadTimeline(); }, [loadTimeline]);

  const handleSearch = (e) => {
    e.preventDefault();
    setUserId(inputId.trim());
  };

  const summary = sessions.reduce((acc, s) => {
    acc[s.status] = (acc[s.status] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
        <div className="flex items-start gap-4">
          <div className="rounded-xl bg-indigo-500/15 p-3">
            <Clock className="h-7 w-7 text-indigo-300" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Attendance Timeline</h1>
            <p className="mt-1 text-sm text-gray-400">Day-by-day attendance history with full punch event breakdown</p>
          </div>
        </div>
      </section>

      {/* Employee Search */}
      <Card>
        <CardContent className="p-5">
          <form onSubmit={handleSearch} className="flex items-end gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Employee User ID</label>
              <div className="flex gap-3">
                <input
                  type="number"
                  value={inputId}
                  onChange={e => setInputId(e.target.value)}
                  placeholder="Enter employee user ID..."
                  className="flex-1 rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <select
                  value={limit}
                  onChange={e => setLimit(Number(e.target.value))}
                  className="rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value={14}>14 days</option>
                  <option value={30}>30 days</option>
                  <option value={60}>60 days</option>
                  <option value={90}>90 days</option>
                </select>
                <Button type="submit" isLoading={loading}>
                  <User className="h-4 w-4" /> Load Timeline
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {!userId && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-12 text-center">
          <Calendar className="h-12 w-12 text-gray-700 mx-auto mb-3" />
          <p className="text-sm text-gray-500">Enter an employee User ID to view their attendance timeline</p>
        </div>
      )}

      {userId && sessions.length > 0 && (
        <>
          {/* Summary bar */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: 'Present', color: '#22c55e', icon: CheckCircle2 },
              { label: 'Late', color: '#f59e0b', icon: AlertTriangle },
              { label: 'Absent', color: '#ef4444', icon: AlertTriangle },
              { label: 'On Leave', color: '#6366f1', icon: Clock },
            ].map(({ label, color, icon: Icon }) => (
              <Card key={label} className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className="text-2xl font-bold text-white mt-1">{summary[label.replace(' ', '_').toUpperCase()] || 0}</p>
                  </div>
                  <Icon className="h-5 w-5" style={{ color }} />
                </div>
              </Card>
            ))}
          </div>

          {/* Timeline */}
          <div className="space-y-2">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-gray-300">{sessions.length} sessions for Employee #{userId}</h2>
              <Button variant="secondary" size="sm" onClick={loadTimeline} isLoading={loading}>
                <RefreshCw className="h-3.5 w-3.5" /> Refresh
              </Button>
            </div>
            {sessions.map(s => (
              <SessionCard
                key={s.id}
                session={s}
                expanded={!!expanded[s.id]}
                onToggle={() => setExpanded(e => ({ ...e, [s.id]: !e[s.id] }))}
              />
            ))}
          </div>
        </>
      )}

      {userId && !loading && sessions.length === 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-12 text-center">
          <Activity className="h-12 w-12 text-gray-700 mx-auto mb-3" />
          <p className="text-sm text-gray-500">No attendance sessions found for employee #{userId}</p>
        </div>
      )}
    </div>
  );
}
