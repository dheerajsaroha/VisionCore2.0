/**
 * AttendanceOverview.jsx
 * Displays today's full status breakdown:
 * - Present, Absent, Late, On Leave, Early Departure, Overtime, Attendance Rate
 * - 7-Day Attendance Trend Volume (AreaChart)
 * - Department Attendance Comparison (BarChart / Progress Bars)
 * - Live Recent Biometric Check-ins
 * - Direct link into the full Attendance module.
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Clock,
  ArrowRight, Activity, Building2, TrendingUp
} from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, BarChart, Bar
} from 'recharts';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Skeleton } from '../ui/Skeleton';
import { formatTime, titleCase } from '../../lib/utils';
import { BiometricAvatar } from '../directory/BiometricAvatar';

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900/95 border border-slate-700/80 rounded-xl px-3 py-2 shadow-2xl backdrop-blur-md text-xs">
      <p className="font-semibold text-slate-400">{label}</p>
      <p className="font-bold text-indigo-400 mt-0.5">{payload[0].value} check-ins recorded</p>
    </div>
  );
};

export function AttendanceOverview({ logs = [], chartData = [], departmentData = [], stats, loading, onSelectUser }) {
  const navigate = useNavigate();
  const [activeView, setActiveView] = useState('trend'); // 'trend' | 'departments'

  if (loading) {
    return (
      <Card className="border-slate-800/80 bg-slate-900/60 p-6">
        <div className="space-y-4">
          <Skeleton className="h-6 w-48 bg-slate-800" />
          <Skeleton className="h-64 bg-slate-800/60 rounded-xl" />
        </div>
      </Card>
    );
  }

  const todayStatusBadges = [
    { label: 'Present Today', count: stats?.todayCheckins ?? stats?.present ?? 0, color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
    { label: 'On Time', count: stats?.onTime ?? 0, color: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20' },
    { label: 'Late Arrival', count: stats?.late ?? 0, color: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
    { label: 'Absent', count: stats?.absent ?? 0, color: 'text-rose-400 bg-rose-500/10 border-rose-500/20' },
    { label: 'On Leave', count: stats?.onLeave ?? 0, color: 'text-purple-400 bg-purple-500/10 border-purple-500/20' },
    { label: 'Early Departure', count: stats?.earlyDeparture ?? 0, color: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20' },
    { label: 'Overtime', count: stats?.overtime ?? 0, color: 'text-violet-400 bg-violet-500/10 border-violet-500/20' },
  ];

  const defaultDeptData = [
    { department: 'Engineering', total: 48, present: 45, rate: 93.8 },
    { department: 'Product & Design', total: 24, present: 23, rate: 95.8 },
    { department: 'Operations', total: 15, present: 14, rate: 93.3 },
    { department: 'Sales & Marketing', total: 30, present: 28, rate: 93.3 },
  ];

  const deptComparison = departmentData.length > 0 ? departmentData : defaultDeptData;

  return (
    <Card className="border-slate-800/80 bg-slate-900/60 shadow-xl overflow-hidden">
      <CardHeader className="border-b border-slate-800/60 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-indigo-400" />
              <CardTitle className="text-slate-100 text-lg">Attendance Intelligence & Real-Time Feed</CardTitle>
            </div>
            <CardDescription className="text-slate-400 text-xs mt-0.5">
              Live biometric authentication stream, 7-day volume trajectory, and departmental compliance
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            {/* View Switcher */}
            <div className="flex items-center gap-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800/80 text-xs">
              <button
                onClick={() => setActiveView('trend')}
                className={`px-2.5 py-1 rounded-lg transition-colors font-medium ${
                  activeView === 'trend'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                7-Day Trend
              </button>
              <button
                onClick={() => setActiveView('departments')}
                className={`px-2.5 py-1 rounded-lg transition-colors font-medium ${
                  activeView === 'departments'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Department Rates
              </button>
            </div>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/dashboard/attendance')}
              className="text-xs text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10"
            >
              Attendance Module
              <ArrowRight className="h-3.5 w-3.5 ml-1" />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-6">
        {/* Status Badges Bar */}
        <div className="flex items-center flex-wrap gap-2.5 mb-6">
          {todayStatusBadges.map((b) => (
            <div
              key={b.label}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-medium ${b.color}`}
            >
              <span>{b.label}:</span>
              <span className="font-bold">{b.count}</span>
            </div>
          ))}
          {stats?.attendanceRate !== undefined && (
            <div className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-xs font-bold">
              <TrendingUp className="h-3.5 w-3.5" />
              <span>{stats.attendanceRate}% Compliance Rate</span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Visual: 7-Day Trend OR Department Comparison */}
          <div className="lg:col-span-2 bg-slate-950/40 border border-slate-800/60 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                {activeView === 'trend' ? (
                  <>
                    <Activity className="h-4 w-4 text-emerald-400" />
                    7-Day Biometric Attendance Volume
                  </>
                ) : (
                  <>
                    <Building2 className="h-4 w-4 text-indigo-400" />
                    Department Attendance Comparison
                  </>
                )}
              </h4>
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-[10px]">
                Biometric Sync Active
              </Badge>
            </div>

            <div className="h-64">
              {activeView === 'trend' ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="attGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.35} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" />
                    <XAxis dataKey="name" stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="checkins"
                      stroke="#10b981"
                      strokeWidth={2.5}
                      fill="url(#attGrad)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={deptComparison} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" />
                    <XAxis dataKey="department" stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="present" fill="#6366f1" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Recent Live Activity Stream */}
          <div className="bg-slate-950/40 border border-slate-800/60 rounded-2xl p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-bold text-slate-200">Recent Check-ins</h4>
                <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-semibold bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Live Feed
                </span>
              </div>

              {logs.length === 0 ? (
                <div className="text-center py-8 text-slate-500 text-xs">
                  <Clock className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  No check-in logs recorded today.
                </div>
              ) : (
                <div className="space-y-2.5 max-h-56 overflow-y-auto custom-scrollbar pr-1">
                  {logs.slice(0, 5).map((log) => (
                    <div
                      key={log.id}
                      onClick={() => onSelectUser && onSelectUser(log.user_id)}
                      className="flex items-center justify-between p-2.5 rounded-xl bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800/60 transition-all cursor-pointer group"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <BiometricAvatar
                          userId={log.user_id}
                          name={log.user_name}
                          size="h-8 w-8"
                          textClass="text-xs"
                          className="group-hover:ring-1 group-hover:ring-indigo-500/40 transition-all"
                        />
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-slate-200 group-hover:text-indigo-300 transition-colors leading-tight truncate">
                            {log.user_name || `Employee #${log.user_id}`}
                          </p>
                          <p className="text-[10px] text-slate-500 mt-0.5">
                            {formatTime(log.check_in)} · {log.dept_name || 'Staff'}
                          </p>
                        </div>
                      </div>

                      <Badge
                        variant={log.status === 'on_time' ? 'success' : log.status === 'late' ? 'warning' : 'default'}
                        className="text-[10px] px-2 py-0.5 shrink-0"
                      >
                        {titleCase(log.status || 'Check-in')}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/dashboard/attendance-timeline')}
              className="w-full mt-4 text-xs border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800"
            >
              View Full Timeline
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
export default AttendanceOverview;
