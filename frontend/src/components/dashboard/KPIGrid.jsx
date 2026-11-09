/**
 * KPIGrid.jsx
 * Role-aware executive KPI metrics grid with loading skeletons and trend indicators.
 */
import React from 'react';
import { motion } from 'framer-motion';
import {
  Users, UserCheck, UserX, Clock,
  Calendar, CheckSquare, Award, Briefcase,
  Activity, ShieldCheck, FileCheck,
  DollarSign, TrendingUp, TrendingDown
} from 'lucide-react';
import { Card, CardContent } from '../ui/Card';
import { SkeletonCard } from '../ui/Skeleton';
import { cn } from '../../lib/utils';

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.05 } },
};

const cardVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

export function KPICard({ title, value, subtitle, icon: Icon, accent = 'indigo', trend, onClick }) {
  const accentStyles = {
    indigo: {
      bar: 'bg-indigo-500',
      iconBg: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
      text: 'text-indigo-400',
    },
    emerald: {
      bar: 'bg-emerald-500',
      iconBg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      text: 'text-emerald-400',
    },
    amber: {
      bar: 'bg-amber-500',
      iconBg: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      text: 'text-amber-400',
    },
    rose: {
      bar: 'bg-rose-500',
      iconBg: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      text: 'text-rose-400',
    },
    purple: {
      bar: 'bg-purple-500',
      iconBg: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      text: 'text-purple-400',
    },
    blue: {
      bar: 'bg-blue-500',
      iconBg: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      text: 'text-blue-400',
    },
    cyan: {
      bar: 'bg-cyan-500',
      iconBg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
      text: 'text-cyan-400',
    },
  };

  const style = accentStyles[accent] || accentStyles.indigo;

  return (
    <motion.div variants={cardVariants}>
      <Card
        className={cn(
          "relative overflow-hidden group h-full border-slate-800/80 bg-slate-900/60 hover:bg-slate-900/90 transition-all duration-300",
          onClick && "cursor-pointer hover:border-slate-700"
        )}
        onClick={onClick}
      >
        <span className={cn("absolute left-0 top-0 h-full w-1 rounded-l-xl", style.bar)} />
        <CardContent className="p-5 pl-6">
          <div className="flex items-start justify-between">
            <div className={cn("p-2.5 rounded-xl border transition-transform duration-300 group-hover:scale-105", style.iconBg)}>
              <Icon className="h-5 w-5" />
            </div>

            {trend !== undefined && (
              <div className={cn(
                "flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border",
                trend >= 0
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : "bg-rose-500/10 text-rose-400 border-rose-500/20"
              )}>
                {trend >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                <span>{trend >= 0 ? '+' : ''}{trend}%</span>
              </div>
            )}
          </div>

          <div className="mt-4">
            <h3 className="text-2xl sm:text-3xl font-black text-slate-100 tracking-tight">
              {value}
            </h3>
            <p className="text-xs font-semibold text-slate-400 mt-1 uppercase tracking-wider">
              {title}
            </p>
            {subtitle && (
              <p className="text-[11px] text-slate-500 mt-0.5 font-medium">
                {subtitle}
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export function KPIGrid({ stats, roleName, loading }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4, 5, 6, 7, 8].slice(0, 4).map((i) => (
          <SkeletonCard key={i} className="h-32" />
        ))}
      </div>
    );
  }

  const role = (roleName || '').toLowerCase();

  // SuperAdmin KPI Config
  if (role.includes('super')) {
    return (
      <motion.div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        <KPICard
          title="Active Organizations"
          value={stats?.totalOrganizations ?? 0}
          subtitle="Multi-tenant enterprises"
          icon={Activity}
          accent="purple"
        />
        <KPICard
          title="Total Platform Users"
          value={stats?.totalEmployees ?? 0}
          subtitle="Across all tenants"
          icon={Users}
          accent="indigo"
        />
        <KPICard
          title="Biometric Engine SLA"
          value="99.98%"
          subtitle="Real-time face verification"
          icon={ShieldCheck}
          accent="emerald"
        />
        <KPICard
          title="Active System Policies"
          value={stats?.activePolicies ?? 0}
          subtitle="RBAC & EAAC rules"
          icon={FileCheck}
          accent="cyan"
        />
      </motion.div>
    );
  }

  // Manager KPI Config
  if (role.includes('manager')) {
    return (
      <motion.div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        <KPICard
          title="Team Members"
          value={stats?.teamCount ?? stats?.totalEmployees ?? 0}
          subtitle="Direct reports"
          icon={Users}
          accent="indigo"
        />
        <KPICard
          title="Present Today"
          value={stats?.todayCheckins ?? 0}
          subtitle={`${stats?.presentRate ?? 0}% attendance rate`}
          icon={UserCheck}
          accent="emerald"
        />
        <KPICard
          title="Pending Approvals"
          value={stats?.pendingApprovals ?? 0}
          subtitle="Leaves, expenses & shifts"
          icon={CheckSquare}
          accent="amber"
        />
        <KPICard
          title="Late / Absent"
          value={(stats?.late ?? 0) + (stats?.absent ?? 0)}
          subtitle={`${stats?.late ?? 0} late, ${stats?.absent ?? 0} absent`}
          icon={UserX}
          accent="rose"
        />
      </motion.div>
    );
  }

  // Employee KPI Config
  if (role.includes('employee')) {
    return (
      <motion.div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        <KPICard
          title="Today's Status"
          value={stats?.myCheckedIn ? "Checked In" : "Not Checked In"}
          subtitle={stats?.myCheckInTime ? `Clocked in at ${stats.myCheckInTime}` : "Action required"}
          icon={Clock}
          accent={stats?.myCheckedIn ? "emerald" : "amber"}
        />
        <KPICard
          title="Leave Balance"
          value={`${stats?.leaveBalanceDays ?? 0} Days`}
          subtitle="Annual accrual remaining"
          icon={Calendar}
          accent="indigo"
        />
        <KPICard
          title="Pending Claims"
          value={stats?.myPendingClaims ?? 1}
          subtitle="Reimbursements in review"
          icon={DollarSign}
          accent="cyan"
        />
        <KPICard
          title="Assigned Tasks"
          value={stats?.myTasks ?? 3}
          subtitle="Pending actions"
          icon={Briefcase}
          accent="purple"
        />
      </motion.div>
    );
  }

  // HR Role KPI Config
  if (role.includes('hr')) {
    return (
      <motion.div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        <KPICard
          title="Total Workforce"
          value={stats?.totalEmployees ?? 0}
          subtitle={`${stats?.activeEmployees ?? 0} active personnel`}
          icon={Users}
          accent="indigo"
        />
        <KPICard
          title="Present Today"
          value={stats?.todayCheckins ?? 0}
          subtitle={`${stats?.presentRate ?? 0}% attendance rate`}
          icon={UserCheck}
          accent="emerald"
        />
        <KPICard
          title="Pending Approvals"
          value={stats?.pendingApprovals ?? 0}
          subtitle="Leaves & reimbursements"
          icon={CheckSquare}
          accent="purple"
        />
        <KPICard
          title="Training Completion"
          value={`${stats?.trainingCompletion ?? 0}%`}
          subtitle={`${stats?.openPositions ?? 4} open requisitions`}
          icon={Award}
          accent="cyan"
        />
      </motion.div>
    );
  }

  // Default / OrgAdmin KPI Config
  return (
    <motion.div
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      <KPICard
        title="Total Workforce"
        value={stats?.totalEmployees ?? 0}
        subtitle="Active headcount"
        icon={Users}
        accent="indigo"
      />
      <KPICard
        title="Present Today"
        value={stats?.todayCheckins ?? 0}
        subtitle={`${stats?.onTime ?? 0} on time, ${stats?.late ?? 0} late`}
        icon={UserCheck}
        accent="emerald"
      />
      <KPICard
        title="On Leave / Absent"
        value={(stats?.onLeave ?? 0) + (stats?.absent ?? 0)}
        subtitle={`${stats?.onLeave ?? 0} leave, ${stats?.absent ?? 0} absent`}
        icon={UserX}
        accent="amber"
      />
      <KPICard
        title="Pending Approvals"
        value={stats?.pendingApprovals ?? 0}
        subtitle="Workflow requests"
        icon={CheckSquare}
        accent="purple"
      />
    </motion.div>
  );
}
