/**
 * LeaveOverview.jsx
 * Multi-role leave overview widget showing:
 * - Personal leave balances (Annual, Sick, Casual) for Employees
 * - Team/Org metrics: Pending, Approved, Rejected requests
 * - Employees currently on leave today
 * - Leave utilization rate
 * - Upcoming leave schedule (next 14 days)
 * Scoped automatically to authenticated role.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight, Palmtree
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import '../ui/Badge';
import { Button } from '../ui/Button';
import { Skeleton } from '../ui/Skeleton';
import { formatDate } from '../../lib/utils';

export function LeaveOverview({ leaveSummary, userRole = 'employee', loading }) {
  const navigate = useNavigate();

  if (loading) {
    return (
      <Card className="border-slate-800/80 bg-slate-900/60 p-6">
        <Skeleton className="h-6 w-48 bg-slate-800 mb-4" />
        <Skeleton className="h-40 bg-slate-800/60 rounded-xl" />
      </Card>
    );
  }

  const role = (userRole || '').toLowerCase();
  const isEmployee = role === 'employee' || role === 'user';

  // No invented leave figures. These previously defaulted to 14 approved, 2
  // rejected, 74.5% utilization, and a fixed 18/10/6 day balance breakdown, so
  // a user with no leave requests at all still saw a populated card.
  const pendingCount = leaveSummary?.pendingCount ?? 0;
  const approvedCount = leaveSummary?.approvedCount ?? 0;
  const leaveUtilization = leaveSummary?.leaveUtilization ?? 0;

  const currentlyOnLeave = leaveSummary?.currentlyOnLeave || [];
  const upcomingLeave = leaveSummary?.upcomingLeave || [];

  const myBalances = leaveSummary?.myBalances || [];

  return (
    <Card className="border-slate-800/80 bg-slate-900/60 shadow-xl overflow-hidden h-full flex flex-col justify-between">
      <div>
        <CardHeader className="border-b border-slate-800/60 pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Palmtree className="h-5 w-5 text-indigo-400" />
              <CardTitle className="text-slate-100 text-base">
                {isEmployee ? 'My Leave Balances & Upcoming Time-Off' : 'Leave Schedule & Team Utilization'}
              </CardTitle>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(isEmployee ? '/dashboard/leave-requests' : '/dashboard/leave-management')}
              className="text-xs text-indigo-400 hover:text-indigo-300 p-0"
            >
              {isEmployee ? 'My Requests' : 'Leave Center'}
              <ArrowRight className="h-3.5 w-3.5 ml-1" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-5 space-y-4">
          {isEmployee ? (
            /* Employee View: Leave Balances & Personal Schedule */
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {myBalances.map((b) => (
                  <div key={b.type} className="p-3.5 rounded-xl bg-slate-950/40 border border-slate-800/60 flex flex-col justify-between">
                    <div className="flex items-center justify-between text-xs mb-2">
                      <span className="font-semibold text-slate-300">{b.type}</span>
                      <span className="text-slate-500">{b.remaining}/{b.total} left</span>
                    </div>
                    <div className="flex items-baseline justify-between">
                      <span className="text-2xl font-black text-slate-100">{b.remaining}</span>
                      <span className="text-[10px] text-slate-500 font-medium">{b.used} used</span>
                    </div>
                    {/* Progress Bar */}
                    <div className="w-full h-1.5 bg-slate-800 rounded-full mt-2.5 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${b.color}`}
                        style={{ width: `${Math.min(100, (b.remaining / Math.max(1, b.total)) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              {/* Upcoming Leaves for Employee */}
              {upcomingLeave.length > 0 && (
                <div className="p-3 rounded-xl bg-slate-950/40 border border-slate-800/60">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-2">
                    My Upcoming Time Off
                  </span>
                  <div className="space-y-1.5">
                    {upcomingLeave.slice(0, 2).map((ul) => (
                      <div key={ul.id} className="flex items-center justify-between text-xs text-slate-300">
                        <span>{ul.type} ({ul.totalDays} days)</span>
                        <span className="font-mono text-indigo-400">{formatDate(ul.startDate)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs">
                <span className="text-indigo-300 font-medium">Planning time off soon?</span>
                <Button
                  size="sm"
                  onClick={() => navigate('/dashboard/leave-requests')}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs h-8 px-3"
                >
                  Apply Leave
                </Button>
              </div>
            </div>
          ) : (
            /* Manager / Admin View: Comprehensive Utilization & Schedules */
            <div className="space-y-4">
              {/* Metric Counters Grid */}
              <div className="grid grid-cols-3 gap-2 p-3 rounded-xl bg-slate-950/40 border border-slate-800/60 text-center">
                <div>
                  <span className="text-[10px] uppercase font-bold text-amber-400">Pending</span>
                  <p className="text-lg font-black text-slate-100 mt-0.5">{pendingCount}</p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-emerald-400">Approved</span>
                  <p className="text-lg font-black text-slate-100 mt-0.5">{approvedCount}</p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-indigo-400">Utilization</span>
                  <p className="text-lg font-black text-slate-100 mt-0.5">{leaveUtilization}%</p>
                </div>
              </div>

              {/* Currently On Leave Today */}
              <div>
                <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                  Currently On Leave Today ({currentlyOnLeave.length})
                </h5>

                {currentlyOnLeave.length === 0 ? (
                  <p className="text-slate-500 text-xs py-3 text-center bg-slate-950/20 rounded-xl border border-slate-800/40">
                    No team members on leave today.
                  </p>
                ) : (
                  <div className="space-y-2 max-h-40 overflow-y-auto custom-scrollbar pr-1">
                    {currentlyOnLeave.map((item) => (
                      <div key={item.id} className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/40 border border-slate-800/60 text-xs">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="h-7 w-7 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center font-bold text-xs shrink-0">
                            {(item.name || 'E')[0]}
                          </div>
                          <div className="min-w-0">
                            <p className="font-semibold text-slate-200 truncate">{item.name}</p>
                            <p className="text-[10px] text-slate-500">{item.dept} · {item.type}</p>
                          </div>
                        </div>
                        <span className="text-[11px] text-slate-400 font-mono shrink-0 ml-2">
                          Returns {formatDate(item.returnDate)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Upcoming Leaves in next 14 days */}
              {upcomingLeave.length > 0 && (
                <div>
                  <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                    Upcoming Scheduled Leave ({upcomingLeave.length})
                  </h5>
                  <div className="space-y-1.5 max-h-32 overflow-y-auto custom-scrollbar pr-1">
                    {upcomingLeave.map((item) => (
                      <div key={item.id} className="flex items-center justify-between p-2 rounded-lg bg-slate-950/30 border border-slate-800/40 text-xs">
                        <span className="text-slate-300 font-medium truncate">{item.name}</span>
                        <span className="text-[10px] text-indigo-400 font-mono">
                          {formatDate(item.startDate)} ({item.totalDays}d)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </div>
    </Card>
  );
}
export default LeaveOverview;
