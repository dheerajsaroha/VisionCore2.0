/**
 * ApprovalItem.jsx
 * Reusable actionable item for the approval queue with approve and reject actions.
 */
import React from 'react';
import {
  Palmtree, DollarSign, Clock, Package,
  Award, CheckCircle, XCircle, FileText
} from 'lucide-react';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { cn } from '../../lib/utils';

const iconMap = {
  leave: Palmtree,
  reimbursement: DollarSign,
  correction: Clock,
  performance: Award,
  workflow: Package,
};

const colorMap = {
  leave: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  reimbursement: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  correction: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  performance: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
  workflow: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
};

export function ApprovalItem({
  item,
  onApprove,
  onReject,
  processing = false,
  canAction = true,
  className,
}) {
  const itemType = item.item_type || 'workflow';
  const Icon = iconMap[itemType] || FileText;
  const color = colorMap[itemType] || colorMap.workflow;

  return (
    <div
      className={cn(
        'p-3.5 rounded-xl bg-slate-950/40 border border-slate-800/60 hover:border-slate-700/80 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 group',
        className
      )}
    >
      <div className="flex items-start gap-3 min-w-0">
        <div className={cn('p-2.5 rounded-xl border shrink-0', color)}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-xs font-bold text-slate-200 group-hover:text-indigo-300 transition-colors">
              {item.title}
            </p>
            {item.time && (
              <span className="text-[10px] text-slate-500 font-mono">{item.time}</span>
            )}
          </div>
          <p className="text-[11px] text-slate-400 mt-0.5 truncate">
            {item.subtitle}
          </p>
          <div className="flex items-center gap-1.5 mt-1">
            <Badge variant="outline" className="text-[10px] border-slate-800 text-slate-400 bg-slate-900/80">
              {item.category || itemType}
            </Badge>
            {item.priority === 'high' && (
              <Badge variant="danger" className="text-[10px]">
                Urgent
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* The backend 403s the approval action for non-privileged roles, so
          offering the buttons produced a guaranteed error. Hide them. */}
      {canAction && (
      <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
        <Button
          size="xs"
          variant="outline"
          disabled={processing}
          onClick={() => onReject && onReject(item)}
          className="text-xs border-rose-900/50 bg-rose-950/20 text-rose-400 hover:bg-rose-900/40 hover:text-rose-300 h-8 px-2.5"
        >
          <XCircle className="h-3.5 w-3.5 mr-1" />
          Reject
        </Button>
        <Button
          size="xs"
          disabled={processing}
          onClick={() => onApprove && onApprove(item)}
          className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white h-8 px-2.5 shadow-sm"
        >
          <CheckCircle className="h-3.5 w-3.5 mr-1" />
          Approve
        </Button>
      </div>
      )}
    </div>
  );
}
export default ApprovalItem;
