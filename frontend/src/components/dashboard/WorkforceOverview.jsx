/**
 * WorkforceOverview.jsx
 * Provides all 4 required workforce visualizations:
 * 1. Headcount Growth Trend
 * 2. Department Distribution
 * 3. Employment Type Classification
 * 4. Location / Branch Distribution
 * Backed by actual data from the workforce-breakdown API.
 */
import React, { useState } from 'react';
import { 
  Users, Building, PieChart as PieIcon, BarChart3, 
  MapPin, Briefcase, Filter, ChevronRight 
} from 'lucide-react';
import { 
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, 
  Tooltip, CartesianGrid, PieChart, Pie, Cell, BarChart, Bar 
} from 'recharts';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Select } from '../ui/Select';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';

const COLORS = ['#6366f1', '#a855f7', '#ec4899', '#3b82f6', '#10b981', '#f59e0b', '#06b6d4'];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900/95 border border-slate-700/80 rounded-xl px-3 py-2 shadow-2xl backdrop-blur-md text-xs">
      <p className="font-semibold text-slate-300">{label || payload[0].name}</p>
      <div className="flex items-center gap-2 mt-1">
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: payload[0].color || '#6366f1' }} />
        <span className="font-bold text-slate-100">{payload[0].value} {typeof payload[0].value === 'number' ? 'people' : ''}</span>
      </div>
    </div>
  );
};

export function WorkforceOverview({ data, departments = [], onDepartmentChange, loading }) {
  const [selectedDept, setSelectedDept] = useState('all');
  const [viewTab, setViewTab] = useState('headcount'); // 'headcount' | 'types'

  const handleDeptSelect = (deptId) => {
    setSelectedDept(deptId);
    if (onDepartmentChange) {
      onDepartmentChange(deptId);
    }
  };

  if (loading) {
    return (
      <Card className="border-slate-800/80 bg-slate-900/60 p-6">
        <div className="space-y-4">
          <Skeleton className="h-6 w-48 bg-slate-800" />
          <Skeleton className="h-4 w-72 bg-slate-800/60" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
            <Skeleton className="h-60 bg-slate-800/60 rounded-xl" />
            <Skeleton className="h-60 bg-slate-800/60 rounded-xl" />
            <Skeleton className="h-60 bg-slate-800/60 rounded-xl" />
          </div>
        </div>
      </Card>
    );
  }

  // Aggregated server-side from this tenant's own rows. These four series
  // each carried a fixed demo dataset (a 110->142 headcount ramp, a five-way
  // department split, a 105/22/10/5 employment mix, and San Francisco / New
  // York / Remote Global sites) identical to the one the backend used to
  // return, so an unconfigured tenant still saw a full workforce breakdown.
  const headcountTrends = data?.headcountTrends ?? [];
  const deptDistribution = data?.departmentDistribution ?? [];
  const employmentTypes = data?.employmentTypes ?? [];
  const locationDistribution = data?.locationDistribution ?? [];

  const totalHeadcount = data?.totalHeadcount ?? 0;
  const activeHeadcount = data?.activeHeadcount ?? 0;
  const inactiveHeadcount = data?.inactiveHeadcount ?? 0;

  return (
    <Card className="border-slate-800/80 bg-slate-900/60 shadow-xl overflow-hidden">
      <CardHeader className="border-b border-slate-800/60 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-indigo-400" />
              <CardTitle className="text-slate-100 text-lg">Workforce Architecture & Distribution</CardTitle>
            </div>
            <CardDescription className="text-slate-400 text-xs mt-0.5">
              Headcount trends, departmental allocations, employment classifications, and physical branch distribution
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800/80 text-xs">
              <button
                onClick={() => setViewTab('headcount')}
                className={`px-2.5 py-1 rounded-lg transition-colors font-medium ${
                  viewTab === 'headcount'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Growth Trend
              </button>
              <button
                onClick={() => setViewTab('types')}
                className={`px-2.5 py-1 rounded-lg transition-colors font-medium ${
                  viewTab === 'types'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Employment Types
              </button>
            </div>

            <Select
              value={selectedDept}
              onChange={(e) => handleDeptSelect(e.target.value)}
              className="text-xs bg-slate-900 border-slate-800 text-slate-300 w-44"
            >
              <option value="all">All Departments</option>
              {departments.map((d) => (
                <option key={d.id || d.name} value={d.id || d.name}>{d.name}</option>
              ))}
            </Select>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-6 space-y-6">
        {/* Top Summary Micro-Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-xl bg-slate-950/40 border border-slate-800/60 text-xs">
          <div>
            <span className="text-slate-500 font-medium">Total Headcount</span>
            <p className="text-lg font-black text-slate-100 mt-0.5">{totalHeadcount}</p>
          </div>
          <div>
            <span className="text-slate-500 font-medium">Active Personnel</span>
            <p className="text-lg font-black text-emerald-400 mt-0.5">{activeHeadcount}</p>
          </div>
          <div>
            <span className="text-slate-500 font-medium">Departments</span>
            <p className="text-lg font-black text-indigo-400 mt-0.5">{deptDistribution.length}</p>
          </div>
          <div>
            <span className="text-slate-500 font-medium">Active Branches</span>
            <p className="text-lg font-black text-purple-400 mt-0.5">{locationDistribution.length}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Chart Area (Trend or Employment Type) */}
          <div className="lg:col-span-2 bg-slate-950/40 border border-slate-800/60 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h4 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                  {viewTab === 'headcount' ? (
                    <>
                      <BarChart3 className="h-4 w-4 text-indigo-400" />
                      Headcount Trajectory (6-Month Growth)
                    </>
                  ) : (
                    <>
                      <Briefcase className="h-4 w-4 text-indigo-400" />
                      Employment Type Distribution
                    </>
                  )}
                </h4>
                <p className="text-[11px] text-slate-500">
                  {viewTab === 'headcount'
                    ? 'Monitored monthly active personnel curve'
                    : 'Full-time, contractor, part-time, and intern split'}
                </p>
              </div>
              <Badge variant="outline" className="text-xs text-indigo-400 border-indigo-500/30 bg-indigo-500/10">
                Live Postgres Metrics
              </Badge>
            </div>

            <div className="h-60">
              {viewTab === 'headcount' ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={headcountTrends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="hcGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" />
                    <XAxis dataKey="month" stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area 
                      type="monotone" 
                      dataKey="headcount" 
                      stroke="#6366f1" 
                      strokeWidth={2.5} 
                      fill="url(#hcGrad)" 
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={employmentTypes} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" />
                    <XAxis dataKey="name" stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="count" fill="#818cf8" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Department Distribution Donut Chart */}
          <div className="bg-slate-950/40 border border-slate-800/60 rounded-2xl p-5 flex flex-col justify-between">
            <div>
              <h4 className="text-sm font-bold text-slate-200 flex items-center gap-2 mb-1">
                <PieIcon className="h-4 w-4 text-purple-400" />
                Department Breakdown
              </h4>
              <p className="text-[11px] text-slate-500 mb-3">Organizational headcount density</p>

              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={deptDistribution}
                      dataKey="count"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={46}
                      outerRadius={68}
                      paddingAngle={4}
                    >
                      {deptDistribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-3 border-t border-slate-800/60 max-h-28 overflow-y-auto custom-scrollbar">
              {deptDistribution.map((item, idx) => (
                <div key={item.name} className="flex items-center gap-1.5 text-[11px]">
                  <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                  <span className="text-slate-400 truncate">{item.name}</span>
                  <span className="font-semibold text-slate-200 ml-auto">{item.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Location & Branch Distribution Row */}
        <div>
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <MapPin className="h-3.5 w-3.5 text-indigo-400" />
            Branch & Geographic Distribution
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {locationDistribution.map((loc) => (
              <div 
                key={loc.name}
                className="p-3 rounded-xl bg-slate-950/40 border border-slate-800/60 flex items-center justify-between"
              >
                <div>
                  <p className="text-xs font-semibold text-slate-200">{loc.name}</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">{loc.city}, {loc.country}</p>
                </div>
                <div className="text-right">
                  <span className="text-sm font-black text-indigo-400">{loc.count}</span>
                  <p className="text-[9px] text-slate-500 uppercase">Members</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
export default WorkforceOverview;
