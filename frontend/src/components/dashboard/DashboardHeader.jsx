/**
 * DashboardHeader.jsx
 * Header component for the role-aware enterprise command center.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  Building2, Camera, RefreshCw, Plus, 
  Calendar, ShieldCheck, UserCheck, Sparkles 
} from 'lucide-react';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { formatDate } from '../../lib/utils';

export function DashboardHeader({ user, roleName, onRefresh, refreshing, onCheckIn }) {
  const navigate = useNavigate();

  const getRoleBadgeVariant = (role) => {
    const r = (role || '').toLowerCase();
    if (r.includes('super')) return 'purple';
    if (r.includes('admin')) return 'primary';
    if (r.includes('manager')) return 'info';
    return 'secondary';
  };

  const formattedRole = (roleName || 'Employee')
    .replace('_', ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-xl shadow-xl">
      <div className="space-y-1.5">
        <div className="flex items-center flex-wrap gap-2.5">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-100 tracking-tight">
            Command Center
          </h1>
          <Badge 
            variant={getRoleBadgeVariant(roleName)}
            className="px-3 py-1 font-semibold text-xs tracking-wide uppercase shadow-sm"
          >
            {formattedRole}
          </Badge>
          {user?.organization_name && (
            <Badge variant="outline" className="bg-slate-800/60 text-slate-300 border-slate-700 gap-1.5 px-3 py-1 text-xs">
              <Building2 className="h-3.5 w-3.5 text-indigo-400" />
              {user.organization_name}
            </Badge>
          )}
        </div>
        <p className="text-sm text-slate-400 flex items-center gap-2">
          <span>Welcome back, <strong className="text-slate-200 font-semibold">{user?.full_name || 'User'}</strong></span>
          <span className="inline-block h-1 w-1 rounded-full bg-slate-600" />
          <span className="text-slate-500 font-mono text-xs">{formatDate(new Date())}</span>
        </p>
      </div>

      <div className="flex items-center flex-wrap gap-2.5">
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          disabled={refreshing}
          className="border-slate-800 bg-slate-900/80 hover:bg-slate-800 text-slate-300"
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? 'animate-spin text-indigo-400' : ''}`} />
          Refresh
        </Button>

        {roleName.toLowerCase().includes('employee') || roleName.toLowerCase().includes('manager') ? (
          <Button
            onClick={onCheckIn || (() => navigate('/dashboard/attendance'))}
            className="bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-medium shadow-lg shadow-indigo-500/20 transition-all hover:scale-[1.02]"
          >
            <Camera className="h-4 w-4 mr-2" />
            Check In Now
          </Button>
        ) : null}

        {roleName.toLowerCase().includes('admin') || roleName.toLowerCase().includes('hr') ? (
          <Button
            onClick={() => navigate('/dashboard/users')}
            className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-medium shadow-lg shadow-indigo-500/20"
          >
            <UserCheck className="h-4 w-4 mr-2" />
            Manage People
          </Button>
        ) : null}

        {roleName.toLowerCase().includes('super') && (
          <Button
            onClick={() => navigate('/dashboard/tenant-admin')}
            className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-medium shadow-lg shadow-purple-500/20"
          >
            <Building2 className="h-4 w-4 mr-2" />
            Tenant Hub
          </Button>
        )}
      </div>
    </div>
  );
}
