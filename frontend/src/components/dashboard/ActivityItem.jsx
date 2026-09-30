/**
 * ActivityItem.jsx
 * Reusable activity row component displaying actor, description, timestamp, and category badge.
 */
import React from 'react';
import { 
  UserPlus, Clock, Package, FileCheck, 
  ShieldCheck, AlertCircle, CheckCircle2, Activity 
} from 'lucide-react';
import { Badge } from '../ui/Badge';
import { cn } from '../../lib/utils';

const iconMap = {
  user: UserPlus,
  leave: Clock,
  asset: Package,
  policy: FileCheck,
  attendance: CheckCircle2,
  security: ShieldCheck,
  system: Activity,
};

const colorMap = {
  user: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
  leave: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  asset: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  policy: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  attendance: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
  security: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
  system: 'text-slate-400 bg-slate-800/40 border-slate-700/60',
};

export function ActivityItem({
  type = 'system',
  title,
  description,
  timestamp,
  actor,
  onClick,
  className,
}) {
  const Icon = iconMap[type] || Activity;
  const style = colorMap[type] || colorMap.system;

  return (
    <div
      onClick={onClick}
      className={cn(
        'flex items-start justify-between gap-3 p-3 rounded-xl bg-slate-950/40 border border-slate-800/60 hover:bg-slate-900/80 hover:border-slate-700 transition-all',
        onClick && 'cursor-pointer',
        className
      )}
    >
      <div className="flex items-start gap-3 min-w-0">
        <div className={cn('p-2 rounded-xl border shrink-0', style)}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-bold text-slate-200 truncate">
            {title}
          </p>
          <p className="text-[11px] text-slate-400 mt-0.5 break-words">
            {description}
          </p>
          {actor && (
            <span className="inline-block mt-1 text-[10px] text-indigo-400 font-medium">
              By {actor}
            </span>
          )}
        </div>
      </div>

      <span className="text-[10px] text-slate-500 font-mono shrink-0 whitespace-nowrap">
        {timestamp}
      </span>
    </div>
  );
}
export default ActivityItem;
