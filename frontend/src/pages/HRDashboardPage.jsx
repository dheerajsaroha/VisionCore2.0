import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { usePermission } from '../hooks/usePermission';
import { canAccess, resolvePolicy } from '../lib/accessControl';
import api from '../services/apiClient';
import {
  Users, Calendar, DollarSign, Briefcase, Clock, TrendingUp,
  AlertCircle, CheckCircle2, RefreshCw, ChevronRight,
  BarChart3, Building2, Target, Zap, Activity, ArrowUpRight, Shield, Trophy, Package
} from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

const hrService = {
  getCommandCenter: () => api.get('/hr/command-center'),
};

const METRIC_CARDS = [
  {
    key: 'total_employees',
    label: 'Total Employees',
    icon: Users,
    color: 'from-indigo-500 to-violet-600',
    glow: 'shadow-indigo-500/20',
    border: 'border-indigo-500/20',
    suffix: '',
    href: '/dashboard/users',
  },
  {
    key: 'today_attendance_rate',
    label: "Today's Attendance",
    icon: Activity,
    color: 'from-emerald-500 to-teal-600',
    glow: 'shadow-emerald-500/20',
    border: 'border-emerald-500/20',
    suffix: '%',
    href: '/dashboard/attendance',
  },
  {
    key: 'pending_leaves',
    label: 'Pending Leaves',
    icon: Calendar,
    color: 'from-amber-500 to-orange-600',
    glow: 'shadow-amber-500/20',
    border: 'border-amber-500/20',
    suffix: '',
    href: '/dashboard/leave',
    alert: true,
  },
  {
    key: 'monthly_payroll_spend',
    label: 'Monthly Payroll',
    icon: DollarSign,
    color: 'from-cyan-500 to-sky-600',
    glow: 'shadow-cyan-500/20',
    border: 'border-cyan-500/20',
    suffix: '',
    prefix: '₹',
    format: 'currency',
    href: '/dashboard/payroll',
  },
  {
    key: 'open_job_postings',
    label: 'Open Positions',
    icon: Briefcase,
    color: 'from-purple-500 to-fuchsia-600',
    glow: 'shadow-purple-500/20',
    border: 'border-purple-500/20',
    suffix: '',
    href: '/dashboard/recruitment',
  },
  {
    key: 'pending_reviews',
    label: 'Pending Reviews',
    icon: Trophy,
    color: 'from-fuchsia-500 to-pink-600',
    glow: 'shadow-fuchsia-500/20',
    border: 'border-fuchsia-500/20',
    suffix: '',
    href: '/dashboard/performance',
    alert: true,
  },
  {
    key: 'pending_salary_advances',
    label: 'Salary Advances',
    icon: TrendingUp,
    color: 'from-rose-500 to-pink-600',
    glow: 'shadow-rose-500/20',
    border: 'border-rose-500/20',
    suffix: '',
    href: '/dashboard/payroll',
    alert: true,
  },
  {
    key: 'today_present_count',
    label: 'Present Today',
    icon: CheckCircle2,
    color: 'from-lime-500 to-green-600',
    glow: 'shadow-lime-500/20',
    border: 'border-lime-500/20',
    suffix: '',
    href: '/dashboard/attendance',
  },
  {
    key: 'total_active_courses',
    label: 'Active L&D Courses',
    icon: Target,
    color: 'from-teal-500 to-emerald-600',
    glow: 'shadow-teal-500/20',
    border: 'border-teal-500/20',
    suffix: '',
    href: '/dashboard/learning',
  },
  {
    key: 'course_completion_rate',
    label: 'Course Pass Rate',
    icon: Trophy,
    color: 'from-purple-500 to-indigo-600',
    glow: 'shadow-purple-500/20',
    border: 'border-purple-500/20',
    suffix: '%',
    href: '/dashboard/learning',
  },
  {
    key: 'critical_positions_count',
    label: 'Critical Positions',
    icon: Shield,
    color: 'from-rose-500 to-pink-600',
    glow: 'shadow-rose-500/20',
    border: 'border-rose-500/20',
    suffix: '',
    href: '/dashboard/succession',
    alert: true,
  },
  {
    key: 'total_assets',
    label: 'Asset Inventory',
    icon: Package,
    color: 'from-amber-500 to-yellow-600',
    glow: 'shadow-amber-500/20',
    border: 'border-amber-500/20',
    suffix: '',
    href: '/dashboard/assets',
  },
];

const QUICK_LINKS = [
  { label: 'Leave Requests', icon: Calendar, href: '/dashboard/leave', desc: 'Manage approvals & balances', color: 'from-indigo-600 to-violet-700' },
  { label: 'Attendance Logs', icon: Activity, href: '/dashboard/attendance', desc: 'Corrections & regularization', color: 'from-emerald-600 to-teal-700' },
  { label: 'Payroll Center', icon: DollarSign, href: '/dashboard/payroll', desc: 'Slips, advances & grades', color: 'from-cyan-600 to-sky-700' },
  { label: 'Recruitment ATS', icon: Briefcase, href: '/dashboard/open-positions', desc: 'Jobs, candidates & interviews', color: 'from-purple-600 to-fuchsia-700' },
  { label: 'Performance System', icon: Trophy, href: '/dashboard/performance', desc: 'OKRs, KPIs, 360° reviews & PIPs', color: 'from-fuchsia-600 to-pink-700' },
  { label: 'L&D & Training Suite', icon: Target, href: '/dashboard/learning', desc: 'Courses, quizzes, skills & certs', color: 'from-teal-600 to-emerald-700' },
  { label: 'Succession & Career', icon: Shield, href: '/dashboard/succession', desc: '9-box matrix, IDPs & bench strength', color: 'from-rose-600 to-pink-700' },
  { label: 'Team Directory', icon: Users, href: '/dashboard/users', desc: 'Employee profiles & roles', color: 'from-amber-600 to-orange-700' },
  { label: 'Asset Management', icon: Package, href: '/dashboard/assets', desc: 'Inventory, licenses & maintenance', color: 'from-amber-600 to-yellow-700' },
];

function formatMetricValue(key, value, card) {
  if (value === null || value === undefined) return '\u2014';
  if (card.format === 'currency') {
    return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(value);
  }
  if (key === 'today_attendance_rate') return `${Number(value).toFixed(1)}%`;
  return value;
}

export default function HRDashboardPage() {
  const { hasPermission, hasFeature } = usePermission();

  // One gate, shared by the metric cards and the quick links below, so both
  // lists agree with the sidebar and with the route guards.
  const canReach = (href) =>
    canAccess(resolvePolicy(href), { hasPermission, hasFeature, isAuthenticated: true }).allowed;

  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { user } = useAuthStore();
  const navigate = useNavigate();

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await hrService.getCommandCenter();
      setMetrics(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load HR metrics.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.06 } },
  };

  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-8 p-1 sm:p-2"
    >
      {/* ── HERO HEADER ── */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-indigo-950 to-purple-950 p-8 text-white shadow-2xl border border-indigo-500/20">
        <div className="absolute -top-20 -right-20 w-96 h-96 rounded-full bg-indigo-600/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-10 -left-10 w-72 h-72 rounded-full bg-purple-600/10 blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="p-4 rounded-2xl bg-gradient-to-br from-indigo-500/30 to-purple-600/20 border border-indigo-400/30 backdrop-blur-md shadow-xl">
              <BarChart3 className="h-8 w-8 text-indigo-300" />
            </div>
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-white via-indigo-100 to-indigo-300 bg-clip-text text-transparent">
                  HR Command Center
                </h1>
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/25 text-xs font-semibold text-emerald-400">
                  <Zap className="h-3 w-3" /> Live
                </div>
              </div>
              <p className="text-sm text-indigo-200/70">
                Sprint 3 - Unified enterprise HR intelligence &amp; operations console
              </p>
              <p className="text-xs text-indigo-300/50 mt-1">
                Welcome back, <span className="text-indigo-300 font-semibold">{user?.full_name || 'Administrator'}</span>
              </p>
            </div>
          </div>
          <Button
            onClick={fetchMetrics}
            variant="secondary"
            className="bg-white/10 hover:bg-white/20 text-white border-white/10 backdrop-blur"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* ── PERFORMANCE WIDGETS SECTION ── */}
      {metrics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <div className="rounded-2xl bg-slate-900/90 border border-fuchsia-500/20 p-5 shadow-xl">
            <p className="text-xs font-bold text-slate-400 uppercase">Top Performers</p>
            <p className="text-3xl font-black text-white mt-2">{metrics.top_performers_count || 0}</p>
            <p className="text-xs text-slate-500 mt-1">Rated 4.5+ this cycle</p>
          </div>
          <div className="rounded-2xl bg-slate-900/90 border border-rose-500/20 p-5 shadow-xl">
            <p className="text-xs font-bold text-slate-400 uppercase">Bottom Performers</p>
            <p className="text-3xl font-black text-white mt-2">{metrics.bottom_performers_count || 0}</p>
            <p className="text-xs text-slate-500 mt-1">{'Rated < 2.0'}</p>
          </div>
          <div className="rounded-2xl bg-slate-900/90 border border-emerald-500/20 p-5 shadow-xl">
            <p className="text-xs font-bold text-slate-400 uppercase">Top Dept</p>
            <p className="text-3xl font-black text-white mt-2">{metrics.top_performing_department || 'N/A'}</p>
            <p className="text-xs text-slate-500 mt-1">Rating: {metrics.top_department_avg_rating || 0}</p>
          </div>
          <div className="rounded-2xl bg-slate-900/90 border border-emerald-500/20 p-5 shadow-xl">
            <p className="text-xs font-bold text-slate-400 uppercase">Review Completion</p>
            <p className="text-3xl font-black text-white mt-2">{metrics.review_completion_rate || 0}%</p>
            <p className="text-xs text-slate-500 mt-1">{metrics.pending_reviews || 0} pending</p>
          </div>
        </div>
      )}

      {/* ── ERROR BANNER ── */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 flex items-center gap-3"
        >
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span className="text-sm font-medium">{error}</span>
        </motion.div>
      )}

      {/* ── METRICS GRID ── */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Spinner size="xl" className="text-indigo-500" />
        </div>
      ) : (
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5"
        >
          {/* Metric cards and quick links link into modules the caller may not
              hold a permission for, or that their plan does not include. Both
              were rendered unconditionally, so the page advertised Payroll,
              Assets and ATS to users who were refused on click. Filter both
              lists through the same gate the sidebar uses. */}
          {METRIC_CARDS.filter((card) => canReach(card.href)).map((card) => {
            const Icon = card.icon;
            const raw = metrics?.[card.key];
            const value = formatMetricValue(card.key, raw, card);
            const isAlert = card.alert && raw > 0;

            return (
              <motion.div
                key={card.key}
                variants={cardVariants}
                whileHover={{ y: -5, scale: 1.01 }}
                transition={{ duration: 0.2 }}
                className="cursor-pointer"
                onClick={() => navigate(card.href)}
              >
                <div className={`relative overflow-hidden rounded-2xl bg-slate-900/90 border backdrop-blur-xl shadow-xl hover:shadow-2xl transition-all duration-300 ${card.border} ${isAlert ? 'ring-1 ring-amber-500/30' : ''} ${card.glow} shadow-lg`}>
                  <div className={`absolute -top-8 -right-8 w-28 h-28 rounded-full bg-gradient-to-br ${card.color} opacity-10 blur-2xl`} />
                  <div className="relative p-5">
                    <div className="flex items-start justify-between mb-4">
                      <div className={`p-2.5 rounded-xl bg-gradient-to-br ${card.color} shadow-lg`}>
                        <Icon className="h-5 w-5 text-white" />
                      </div>
                      {isAlert && (
                        <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/25 text-amber-400 text-xs font-semibold">
                          <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse" />
                          Pending
                        </div>
                      )}
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-baseline gap-1">
                        {card.prefix && (
                          <span className="text-lg font-bold text-slate-400">{card.prefix}</span>
                        )}
                        <span className="text-3xl font-black text-white tracking-tight">
                          {value}
                        </span>
                      </div>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        {card.label}
                      </p>
                    </div>
                    <div className="mt-4 flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors">
                      <span>View details</span>
                      <ArrowUpRight className="h-3 w-3" />
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </motion.div>
      )}

      {/* ── QUICK LINKS MODULE GRID ── */}
      <div>
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 rounded-xl bg-slate-800 border border-slate-700">
            <Target className="h-4 w-4 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">HR Modules</h2>
            <p className="text-xs text-slate-500">Sprint 3 {'\u2014'} Modules you can access</p>
          </div>
        </div>
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          {QUICK_LINKS.filter((link) => canReach(link.href)).map((link) => {
            const Icon = link.icon;
            return (
              <motion.div
                key={link.href}
                variants={cardVariants}
                whileHover={{ y: -3 }}
                transition={{ duration: 0.2 }}
              >
                <button
                  onClick={() => navigate(link.href)}
                  className="w-full text-left group relative overflow-hidden rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-slate-600 backdrop-blur-xl shadow-lg hover:shadow-xl transition-all duration-300 p-5"
                >
                  <div className={`absolute inset-0 bg-gradient-to-br ${link.color} opacity-0 group-hover:opacity-5 transition-opacity duration-300`} />
                  <div className="relative flex items-center gap-4">
                    <div className={`p-3 rounded-xl bg-gradient-to-br ${link.color} shadow-lg flex-shrink-0`}>
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-bold text-white group-hover:text-indigo-300 transition-colors text-sm">{link.label}</p>
                      <p className="text-xs text-slate-400 mt-0.5 truncate">{link.desc}</p>
                    </div>
                    <ChevronRight className="h-4 w-4 text-slate-600 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all flex-shrink-0" />
                  </div>
                </button>
              </motion.div>
            );
          })}
        </motion.div>
      </div>

      {/* ── SPRINT STATUS FOOTER ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="rounded-2xl bg-slate-900/60 border border-slate-800 p-6 backdrop-blur"
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
              <CheckCircle2 className="h-5 w-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-sm font-bold text-white">Sprint 3 {'\u00B7'} HR Modules {'\u2014'} All Systems Operational</p>
              <p className="text-xs text-slate-500 mt-0.5">5 of 5 modules validated &amp; frozen</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              { label: '\u{1F512} Leave', color: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/25' },
              { label: '\u{1F512} Attendance', color: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25' },
              { label: '\u{1F512} Payroll', color: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/25' },
              { label: '\u{1F512} Recruitment', color: 'bg-purple-500/15 text-purple-400 border-purple-500/25' },
              { label: '\u{1F512} HR Center', color: 'bg-rose-500/15 text-rose-400 border-rose-500/25' },
            ].map((badge) => (
              <span
                key={badge.label}
                className={`inline-flex items-center gap-1 px-3 py-1 rounded-full border text-xs font-semibold ${badge.color}`}
              >
                {badge.label}
              </span>
            ))}
          </div>
        </div>
        <div className="mt-5">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
            <span>Sprint 3 Completion</span>
            <span className="text-emerald-400 font-bold">100%</span>
          </div>
          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-500 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: '100%' }}
              transition={{ duration: 1.2, delay: 0.6, ease: 'easeOut' }}
            />
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

