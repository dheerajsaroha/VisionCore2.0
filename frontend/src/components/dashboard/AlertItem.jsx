/**
 * AlertItem.jsx
 * Reusable alert row component highlighting severity levels, actionable links, and icons.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  AlertTriangle, Clock, FileCheck, Ticket, 
  Award, Calendar, RefreshCw, ArrowRight, ShieldCheck 
} from 'lucide-react';
import { Badge } from '../ui/Badge';
import { cn } from '../../lib/utils';

const iconMap = {
  Attendance: Clock,
  Compliance: FileCheck,
  'IT Desk': Ticket,
  Operations: RefreshCw,
  'L&D': Award,
  Performance: Award,
  Leave: Calendar,
  Scheduling: RefreshCw,
  Security: ShieldCheck,
};

export function AlertItem({
  alert,
  onClick,
  className,
}) {
  const navigate = useNavigate();
  const Icon = iconMap[alert.category] || alert.icon || AlertTriangle;

  const severityBadge = (sev) => {
    switch (sev) {
      case 'high':
        return <Badge variant="danger" className="text-[10px]">High Priority</Badge>;
      case 'medium':
        return <Badge variant="warning" className="text-[10px]">Action Required</Badge>;
      default:
        return <Badge variant="info" className="text-[10px]">Operational</Badge>;
    }
  };

  const handleClick = () => {
    if (onClick) {
      onClick(alert);
    } else if (alert.link) {
      navigate(alert.link);
    }
  };

  return (
    <div
      onClick={handleClick}
      className={cn(
        'p-3.5 rounded-xl bg-slate-950/40 border border-slate-800/60 hover:border-amber-500/40 hover:bg-slate-900/80 transition-all cursor-pointer group flex items-start justify-between gap-3',
        className
      )}
    >
      <div className="flex items-start gap-3 min-w-0">
        <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0 group-hover:scale-105 transition-transform">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-xs font-bold text-slate-200 group-hover:text-amber-300 transition-colors">
              {alert.title}
            </p>
            {severityBadge(alert.severity)}
          </div>
          <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">
            {alert.description}
          </p>
        </div>
      </div>

      <ArrowRight className="h-4 w-4 text-slate-600 group-hover:text-amber-400 transition-colors shrink-0 mt-1" />
    </div>
  );
}
export default AlertItem;
