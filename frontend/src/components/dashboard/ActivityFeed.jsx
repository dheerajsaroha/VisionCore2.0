/**
 * ActivityFeed.jsx
 * Unified recent activity stream with event category filtering and tenant boundaries.
 * Backed by actual AuditLog and real-time database records.
 */
import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  Activity, UserPlus, Clock, CheckCircle2, 
  FileCheck, ShieldAlert, Package, DollarSign, Filter 
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { ActivityItem } from './ActivityItem';

export function ActivityFeed({ activities = [], loading, onFilterChange }) {
  const [filter, setFilter] = useState('all');

  const handleFilterClick = (f) => {
    setFilter(f);
    if (onFilterChange) {
      onFilterChange(f);
    }
  };

  if (loading) {
    return (
      <Card className="border-slate-800/80 bg-slate-900/60 p-6">
        <Skeleton className="h-6 w-48 bg-slate-800 mb-4" />
        <Skeleton className="h-44 bg-slate-800/60 rounded-xl" />
      </Card>
    );
  }

  const list = activities.filter((act) => {
    if (filter === 'all') return true;
    return (act.type || '').toLowerCase() === filter;
  });

  return (
    <Card className="border-slate-800/80 bg-slate-900/60 shadow-xl overflow-hidden h-full">
      <CardHeader className="border-b border-slate-800/60 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-indigo-400" />
            <CardTitle className="text-slate-100 text-base">Real-Time Audit & Activity Stream</CardTitle>
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1.5 text-xs flex-wrap">
            {['all', 'user', 'leave', 'attendance', 'policy', 'asset'].map((f) => (
              <button
                key={f}
                onClick={() => handleFilterClick(f)}
                className={`px-2.5 py-1 rounded-lg capitalize transition-colors font-medium ${
                  filter === f 
                    ? 'bg-indigo-600 text-white shadow-sm' 
                    : 'bg-slate-950/40 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-4 space-y-2.5">
        {list.length === 0 ? (
          <div className="py-8">
            <EmptyState
              title="No Activities"
              description={`No recent activities recorded for the "${filter}" filter category.`}
              icon={Activity}
            />
          </div>
        ) : (
          list.slice(0, 6).map((act) => (
            <ActivityItem
              key={act.id}
              type={act.type}
              title={act.title}
              description={act.description}
              timestamp={act.timestamp}
              actor={act.actor}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}
export default ActivityFeed;
