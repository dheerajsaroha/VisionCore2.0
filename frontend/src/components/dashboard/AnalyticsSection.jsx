/**
 * AnalyticsSection.jsx
 * Comprehensive interactive multi-dimensional analytics:
 * - Attendance Compliance (On-Time vs Late vs Absent)
 * - Leave Utilization (Annual vs Sick vs Casual)
 * - Hiring Velocity (Joined vs Left vs Open Positions)
 * - Performance Ratings (1-5 Star Bell-Curve / Distribution)
 * - Cost & Payroll (Gross vs Net Trajectory)
 * Readable, responsive, theme-aware, and data-driven.
 */
import React, { useState } from 'react';
import {
  BarChart3, Activity
} from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend
} from 'recharts';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card';
import { Skeleton } from '../ui/Skeleton';

const CustomChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900/95 border border-slate-700/80 rounded-xl px-3.5 py-2.5 shadow-2xl backdrop-blur-md text-xs">
      <p className="font-bold text-slate-300 mb-1">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 mt-0.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
          <span className="text-slate-400 capitalize">{p.name}:</span>
          <span className="font-bold text-slate-100">
            {typeof p.value === 'number' && p.value > 1000 ? `$${p.value.toLocaleString()}` : p.value}
            {p.unit || ''}
          </span>
        </div>
      ))}
    </div>
  );
};

export function AnalyticsSection({ data, loading }) {
  const [activeTab, setActiveTab] = useState('attendance');

  if (loading) {
    return (
      <Card className="border-slate-800/80 bg-slate-900/60 p-6">
        <Skeleton className="h-6 w-48 bg-slate-800 mb-4" />
        <Skeleton className="h-64 bg-slate-800/60 rounded-xl" />
      </Card>
    );
  }

  // These series are aggregated server-side from this tenant's own rows.
  // They previously each carried a `||` fallback holding a fixed demo dataset
  // that was byte-identical to the one the backend used to return, so an
  // organization with no attendance, leave, hiring, review, or payroll records
  // still saw a fully populated analytics board. There is no sample data here
  // on purpose: a tab with nothing to show says so.
  const attendanceRateData = data?.attendanceCompliance ?? [];
  const leaveUtilizationData = data?.leaveUtilization ?? [];
  const hiringTrendsData = data?.hiringTrends ?? [];
  const perfDistribution = data?.performanceDistribution ?? [];
  const payrollCosts = data?.payrollCosts ?? [];
  const openPositions = data?.openPositions ?? 0;
  const hasData = data?.hasData ?? {};

  // Leave series are derived from the leave types this tenant actually uses,
  // rather than a fixed annual/sick/casual trio.
  const leaveTypes = Array.from(
    leaveUtilizationData.reduce((acc, row) => {
      Object.keys(row.byType ?? {}).forEach((t) => acc.add(t));
      return acc;
    }, new Set())
  );
  const LEAVE_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#38bdf8', '#a855f7', '#f43f5e'];

  const TAB_DATA = {
    attendance: { rows: attendanceRateData, populated: hasData.attendanceCompliance },
    leave: { rows: leaveUtilizationData, populated: hasData.leaveUtilization },
    hiring: { rows: hiringTrendsData, populated: hasData.hiringTrends },
    performance: { rows: perfDistribution, populated: hasData.performanceDistribution },
    payroll: { rows: payrollCosts, populated: hasData.payrollCosts },
  };
  const activeTabState = TAB_DATA[activeTab] ?? { rows: [], populated: false };
  const TAB_EMPTY = {
    attendance: 'No attendance sessions recorded in the last 7 days.',
    leave: 'No leave requests in the last 6 months.',
    hiring: 'No hires or departures in the last 6 months.',
    performance: 'No completed performance reviews.',
    payroll: 'No payroll records in the last 6 months.',
  };

  return (
    <Card className="border-slate-800/80 bg-slate-900/60 shadow-xl overflow-hidden">
      <CardHeader className="border-b border-slate-800/60 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-indigo-400" />
              <CardTitle className="text-slate-100 text-lg">Enterprise Workforce Analytics</CardTitle>
            </div>
            <CardDescription className="text-slate-400 text-xs mt-0.5">
              Deep analytical trends across compliance, utilization, hiring velocity, appraisals, and payroll
            </CardDescription>
          </div>

          {/* Analytics Tabs */}
          <div className="flex items-center gap-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800/80 text-xs font-medium flex-wrap">
            <button
              onClick={() => setActiveTab('attendance')}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === 'attendance'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Attendance
            </button>
            <button
              onClick={() => setActiveTab('leave')}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === 'leave'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Leave
            </button>
            <button
              onClick={() => setActiveTab('hiring')}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === 'hiring'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Hiring
            </button>
            <button
              onClick={() => setActiveTab('performance')}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === 'performance'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Performance
            </button>
            <button
              onClick={() => setActiveTab('payroll')}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === 'payroll'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Cost & Payroll
            </button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-6">
        {activeTabState.populated ? (
          <div className="h-72">
            {activeTab === 'attendance' && (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={attendanceRateData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" />
                  <XAxis dataKey="day" stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#475569" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<CustomChartTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                  <Bar dataKey="onTime" name="On Time" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="late" name="Late" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="absent" name="Absent" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}

            {activeTab === 'leave' && (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={leaveUtilizationData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" />
                  <XAxis dataKey="month" stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#475569" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<CustomChartTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                  {leaveTypes.map((type, i) => (
                    <Area
                      key={type}
                      type="monotone"
                      dataKey={`byType.${type}`}
                      name={type}
                      stroke={LEAVE_COLORS[i % LEAVE_COLORS.length]}
                      fill={LEAVE_COLORS[i % LEAVE_COLORS.length]}
                      fillOpacity={0.15}
                      strokeWidth={2}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            )}

            {activeTab === 'hiring' && (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hiringTrendsData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" />
                  <XAxis dataKey="month" stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#475569" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<CustomChartTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                  <Bar dataKey="joined" name="Joined" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="left" name="Departed" fill="#ec4899" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}

            {activeTab === 'performance' && (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={perfDistribution} layout="vertical" margin={{ top: 10, right: 20, left: 60, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#1e293b" />
                  <XAxis type="number" stroke="#475569" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                  <YAxis type="category" dataKey="rating" stroke="#94a3b8" fontSize={10} tickLine={false} axisLine={false} width={130} />
                  <Tooltip content={<CustomChartTooltip />} />
                  <Bar dataKey="count" name="Evaluated Employees" fill="#818cf8" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}

            {activeTab === 'payroll' && (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={payrollCosts} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="totalPayGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="basePayGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" />
                  <XAxis dataKey="month" stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#475569" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v / 1000}k`} />
                  <Tooltip content={<CustomChartTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                  <Area type="monotone" dataKey="total" name="Total Expenditure" stroke="#6366f1" fill="url(#totalPayGrad)" strokeWidth={2} />
                  <Area type="monotone" dataKey="base" name="Base Salary" stroke="#38bdf8" fill="url(#basePayGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        ) : (
          <div className="h-72 flex flex-col items-center justify-center gap-2 text-center">
            <Activity className="h-8 w-8 text-slate-700" />
            <p className="text-sm font-medium text-slate-300">No data for this period</p>
            <p className="text-xs text-slate-500 max-w-sm">{TAB_EMPTY[activeTab]}</p>
            {activeTab === 'hiring' && (
              <p className="text-xs text-slate-500">
                Open requisitions right now: <span className="font-semibold text-slate-300">{openPositions}</span>
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
export default AnalyticsSection;
