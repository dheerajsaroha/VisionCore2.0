import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Users,
  Clock,
  TrendingUp,
  AlertTriangle,
  Camera,
  Ticket,
  Receipt,
  ArrowRight,
  ShieldCheck,
  Building2,
  Briefcase,
  CheckCircle2,
  Calendar,
  Award,
  Activity,
  FileText,
  UserCheck
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { attendanceService } from '../services/attendanceService';
import { userService } from '../services/userService';
import { ticketService } from '../services/ticketService';
import { useAuthStore } from '../store/authStore';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { formatTime, formatDate, titleCase, cn } from '../lib/utils';

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } }
};

export default function Overview() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);

  const roleName = (user?.role?.name || '').toLowerCase();

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [logsRes, usersRes, ticketsRes] = await Promise.all([
        attendanceService.getLogs({ limit: 100 }).catch(() => ({ data: [] })),
        userService.getUsers().catch(() => ({ data: [] })),
        ticketService.getTickets({ limit: 10 }).catch(() => ({ data: [] })),
      ]);

      const allLogs = logsRes.data || [];
      const allUsers = usersRes.data || [];
      const allTickets = ticketsRes.data || [];

      const today = new Date().toDateString();
      const todayLogs = allLogs.filter(
        (l) => new Date(l.check_in).toDateString() === today
      );

      setStats({
        totalEmployees: allUsers.length,
        todayCheckins: todayLogs.length,
        onTime: todayLogs.filter((l) => l.status === 'on_time').length,
        late: todayLogs.filter((l) => l.status === 'late').length,
        openTickets: allTickets.filter((t) => t.status === 'open').length,
      });

      setLogs(allLogs.slice(0, 8));
      setTickets(allTickets.slice(0, 4));

      const days = [];
      for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        const dayStr = d.toDateString();

        const count = allLogs.filter(
          (l) => new Date(l.check_in).toDateString() === dayStr
        ).length;

        days.push({
          name: d.toLocaleDateString('en', { weekday: 'short' }),
          checkins: count,
        });
      }
      setChartData(days);
    } catch (err) {
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  const StatCard = ({ icon: Icon, label, value, trend, bgClass }) => (
    <motion.div variants={itemVariants}>
      <Card className="h-full border-0 relative overflow-hidden group">
        <div className={cn("absolute top-0 left-0 w-1 h-full", bgClass)} />
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div className={cn(`h-12 w-12 rounded-xl flex items-center justify-center transition-transform group-hover:scale-110`, bgClass)}>
              <Icon className="h-6 w-6 text-white" />
            </div>
            {trend !== undefined && (
              <span className={cn(`text-xs font-bold px-2 py-1 rounded-full bg-slate-100 dark:bg-slate-800`, trend >= 0 ? 'text-green-500' : 'text-red-500')}>
                {trend >= 0 ? '+' : ''}{trend}%
              </span>
            )}
          </div>
          <div className="mt-5">
            <p className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">{value}</p>
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400 mt-1">{label}</p>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spinner size="xl" className="text-primary-500" />
      </div>
    );
  }

  // ── Render 1: SuperAdmin Dashboard ─────────────────────────────────────────
  if (roleName.includes('super')) {
    return (
      <motion.div className="space-y-8" variants={containerVariants} initial="hidden" animate="visible">
        <motion.div variants={itemVariants} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Badge className="bg-purple-600 text-white border-0 px-3 py-1 font-semibold">SuperAdmin</Badge>
              <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">Platform Command Center</h1>
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Multi-tenant management & platform governance</p>
          </div>
          <div className="flex gap-3">
            <Button onClick={() => navigate('/dashboard/tenant-admin')} className="bg-purple-600 hover:bg-purple-700 text-white">
              <Building2 className="mr-2 h-4 w-4" /> Tenant Admin
            </Button>
            <Button onClick={() => navigate('/dashboard/ai-governance')} variant="secondary">
              <ShieldCheck className="mr-2 h-4 w-4" /> System Governance
            </Button>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard icon={Building2} label="Active Organizations" value={12} bgClass="bg-purple-600" />
          <StatCard icon={Users} label="Total Managed Users" value={stats?.totalEmployees || 0} bgClass="bg-blue-600" />
          <StatCard icon={Activity} label="AI Biometric Engine" value="99.98%" bgClass="bg-emerald-500" />
          <StatCard icon={ShieldCheck} label="Active Security Policies" value={8} bgClass="bg-amber-500" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Platform Biometric Activity</CardTitle>
              <CardDescription>7-day cross-tenant check-in volume</CardDescription>
            </CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Area type="monotone" dataKey="checkins" stroke="#9333ea" fill="#f3e8ff" />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Platform Control Actions</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <Button variant="secondary" className="w-full justify-between" onClick={() => navigate('/dashboard/tenant-admin')}>
                <span>Manage Multi-Tenant Accounts</span> <ArrowRight className="h-4 w-4" />
              </Button>
              <Button variant="secondary" className="w-full justify-between" onClick={() => navigate('/dashboard/permissions')}>
                <span>Dynamic RBAC & EAAC Policies</span> <ArrowRight className="h-4 w-4" />
              </Button>
              <Button variant="secondary" className="w-full justify-between" onClick={() => navigate('/dashboard/ai-usage')}>
                <span>AI Models & API Consumption</span> <ArrowRight className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        </div>
      </motion.div>
    );
  }

  // ── Render 2: HR Dashboard ─────────────────────────────────────────────────
  if (roleName.includes('hr')) {
    return (
      <motion.div className="space-y-8" variants={containerVariants} initial="hidden" animate="visible">
        <motion.div variants={itemVariants} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <Badge className="bg-indigo-600 text-white border-0 px-3 py-1 font-semibold mb-2">HR Command Center</Badge>
            <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white">Human Resources Dashboard</h1>
          </div>
          <div className="flex gap-3">
            <Button onClick={() => navigate('/dashboard/hr')} className="bg-indigo-600 hover:bg-indigo-500">
              <Briefcase className="mr-2 h-4 w-4" /> HR Analytics
            </Button>
            <Button onClick={() => navigate('/dashboard/users')} variant="secondary">
              <Users className="mr-2 h-4 w-4" /> Employee Directory
            </Button>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard icon={Users} label="Headcount" value={stats?.totalEmployees || 0} bgClass="bg-indigo-600" />
          <StatCard icon={CheckCircle2} label="Present Today" value={stats?.todayCheckins || 0} bgClass="bg-emerald-500" />
          <StatCard icon={Calendar} label="On Leave Today" value={2} bgClass="bg-amber-500" />
          <StatCard icon={Award} label="Open Regularizations" value={stats?.openTickets || 0} bgClass="bg-rose-500" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2">
            <CardHeader><CardTitle>Workforce Attendance Trends</CardTitle></CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Area type="monotone" dataKey="checkins" stroke="#4f46e5" fill="#e0e7ff" />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>HR Quick Actions</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <Button variant="secondary" className="w-full justify-between" onClick={() => navigate('/dashboard/leave')}>
                <span>Manage Leave Requests</span> <ArrowRight className="h-4 w-4" />
              </Button>
              <Button variant="secondary" className="w-full justify-between" onClick={() => navigate('/dashboard/payroll')}>
                <span>Process Monthly Payroll</span> <ArrowRight className="h-4 w-4" />
              </Button>
              <Button variant="secondary" className="w-full justify-between" onClick={() => navigate('/dashboard/performance')}>
                <span>Performance Reviews</span> <ArrowRight className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        </div>
      </motion.div>
    );
  }

  // ── Render 3: Manager Dashboard ────────────────────────────────────────────
  if (roleName.includes('manager')) {
    return (
      <motion.div className="space-y-8" variants={containerVariants} initial="hidden" animate="visible">
        <motion.div variants={itemVariants} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <Badge className="bg-teal-600 text-white border-0 px-3 py-1 font-semibold mb-2">Team Operations</Badge>
            <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white">Manager Workspace</h1>
          </div>
          <Button onClick={() => navigate('/dashboard/attendance')} className="bg-teal-600 hover:bg-teal-500">
            <Camera className="mr-2 h-4 w-4" /> Team Kiosk Check-In
          </Button>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard icon={Users} label="Team Direct Reports" value={stats?.totalEmployees || 0} bgClass="bg-teal-600" />
          <StatCard icon={Clock} label="Today's Check-ins" value={stats?.todayCheckins || 0} bgClass="bg-emerald-500" />
          <StatCard icon={TrendingUp} label="On Time Rate" value="94%" bgClass="bg-indigo-500" />
          <StatCard icon={AlertTriangle} label="Pending Approvals" value={stats?.openTickets || 0} bgClass="bg-amber-500" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2">
            <CardHeader><CardTitle>Team Attendance History</CardTitle></CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Area type="monotone" dataKey="checkins" stroke="#0d9488" fill="#ccfbf1" />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Manager Workflow Actions</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <Button variant="secondary" className="w-full justify-between" onClick={() => navigate('/dashboard/approval-workflows')}>
                <span>Approve Attendance Regularization</span> <ArrowRight className="h-4 w-4" />
              </Button>
              <Button variant="secondary" className="w-full justify-between" onClick={() => navigate('/dashboard/leave')}>
                <span>Approve Team Leaves</span> <ArrowRight className="h-4 w-4" />
              </Button>
              <Button variant="secondary" className="w-full justify-between" onClick={() => navigate('/dashboard/reports')}>
                <span>Generate Team Reports</span> <ArrowRight className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        </div>
      </motion.div>
    );
  }

  // ── Render 4: Candidate / Recruitment Dashboard ───────────────────────────
  if (roleName.includes('candidate')) {
    return (
      <motion.div className="space-y-8" variants={containerVariants} initial="hidden" animate="visible">
        <motion.div variants={itemVariants} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <Badge className="bg-sky-600 text-white border-0 px-3 py-1 font-semibold mb-2">Recruitment Portal</Badge>
            <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white">Candidate Dashboard</h1>
          </div>
          <Button onClick={() => navigate('/dashboard/open-positions')} className="bg-sky-600 hover:bg-sky-500">
            <Briefcase className="mr-2 h-4 w-4" /> Browse Open Positions
          </Button>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <StatCard icon={FileText} label="Submitted Applications" value={1} bgClass="bg-sky-600" />
          <StatCard icon={UserCheck} label="Interview Status" value="Under Review" bgClass="bg-emerald-500" />
          <StatCard icon={Briefcase} label="Available Roles" value={5} bgClass="bg-indigo-500" />
        </div>

        <Card>
          <CardHeader><CardTitle>Recruitment Quick Actions</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Button variant="secondary" className="w-full justify-between" onClick={() => navigate('/dashboard/open-positions')}>
              <span>View Available Job Openings</span> <ArrowRight className="h-4 w-4" />
            </Button>
            <Button variant="secondary" className="w-full justify-between" onClick={() => navigate('/dashboard/candidate-pipeline')}>
              <span>Check Application Status</span> <ArrowRight className="h-4 w-4" />
            </Button>
          </CardContent>
        </Card>
      </motion.div>
    );
  }

  // ── Render 5: Employee / Personal Workspace (Default) ─────────────────────
  return (
    <motion.div 
      className="space-y-6 lg:space-y-8"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header */}
      <motion.div variants={itemVariants} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <Badge className="bg-blue-600 text-white border-0 px-3 py-1 font-semibold mb-2">Personal Workspace</Badge>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">Overview</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Welcome back, <span className="font-semibold text-slate-700 dark:text-slate-300">{user?.full_name || 'User'}</span>
          </p>
        </div>
        <Button onClick={() => navigate('/dashboard/attendance')} className="shadow-lg shadow-primary-500/30 hover:scale-105 transition-transform bg-indigo-600 text-white">
          <Camera className="mr-2 h-5 w-5" />
          Biometric Check In
        </Button>
      </motion.div>

      {/* Stats Bento */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6">
        <StatCard icon={Users} label="Organization Total" value={stats?.totalEmployees || 0} bgClass="bg-blue-600" />
        <StatCard icon={Clock} label="Today's Check-ins" value={stats?.todayCheckins || 0} bgClass="bg-emerald-500" />
        <StatCard icon={TrendingUp} label="On Time Rate" value={stats?.onTime || 0} bgClass="bg-indigo-500" trend={12} />
        <StatCard icon={AlertTriangle} label="Open Support Tickets" value={stats?.openTickets || 0} bgClass="bg-amber-500" />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">
        {/* Chart */}
        <motion.div variants={itemVariants} className="lg:col-span-2 h-full">
          <Card className="h-full flex flex-col">
            <CardHeader className="pb-2">
              <CardTitle>Attendance Trends</CardTitle>
              <CardDescription>7-day check-in history</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 min-h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorCheckins" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <Tooltip 
                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                  />
                  <Area type="monotone" dataKey="checkins" stroke="#6366f1" strokeWidth={3} fill="url(#colorCheckins)" />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>

        {/* Quick Actions Stack */}
        <motion.div variants={itemVariants} className="flex flex-col gap-4 lg:gap-6">
          <Card className="flex-1 bg-gradient-to-br from-indigo-500 to-purple-600 border-0 text-white">
            <CardHeader>
              <CardTitle className="text-white">Quick Actions</CardTitle>
              <CardDescription className="text-indigo-100">Need something done fast?</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <button onClick={() => navigate('/dashboard/ticketing')} className="w-full flex items-center justify-between p-3 bg-white/10 hover:bg-white/20 rounded-xl transition-colors backdrop-blur-sm border border-white/10">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-white/10 rounded-lg"><Ticket className="h-4 w-4" /></div>
                  <span className="font-medium text-sm">Open IT Ticket</span>
                </div>
                <ArrowRight className="h-4 w-4 opacity-50" />
              </button>
              <button onClick={() => navigate('/dashboard/reimbursements')} className="w-full flex items-center justify-between p-3 bg-white/10 hover:bg-white/20 rounded-xl transition-colors backdrop-blur-sm border border-white/10">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-white/10 rounded-lg"><Receipt className="h-4 w-4" /></div>
                  <span className="font-medium text-sm">Submit Expense</span>
                </div>
                <ArrowRight className="h-4 w-4 opacity-50" />
              </button>
              <button onClick={() => navigate('/dashboard/leave')} className="w-full flex items-center justify-between p-3 bg-white/10 hover:bg-white/20 rounded-xl transition-colors backdrop-blur-sm border border-white/10">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-white/10 rounded-lg"><Calendar className="h-4 w-4" /></div>
                  <span className="font-medium text-sm">Apply for Leave</span>
                </div>
                <ArrowRight className="h-4 w-4 opacity-50" />
              </button>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Activity & Tickets Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 lg:gap-6">
        {/* Activity */}
        <motion.div variants={itemVariants}>
          <Card className="h-full">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Recent Check-ins</CardTitle>
                <CardDescription>Live feed of organization activity</CardDescription>
              </div>
              <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard/attendance')} className="text-primary-600 hover:bg-primary-50">
                View All
              </Button>
            </CardHeader>
            <CardContent>
              {logs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-slate-400">
                  <Clock className="h-8 w-8 mb-2 opacity-50" />
                  <p className="text-sm">No activity recorded yet</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {logs.map((log) => (
                    <div key={log.id} className="flex items-center justify-between py-3 px-2 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded-xl transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-full bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold text-sm">
                          {(log.user_name || 'U')[0].toUpperCase()}
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-900 dark:text-white">{log.user_name || 'User'}</p>
                          <p className="text-xs text-slate-500 dark:text-slate-400">{formatDate(log.check_in)} at {formatTime(log.check_in)}</p>
                        </div>
                      </div>
                      <Badge variant={log.status === 'on_time' ? 'success' : log.status === 'late' ? 'warning' : 'default'} className="px-3 py-1">
                        {titleCase(log.status)}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Tickets */}
        <motion.div variants={itemVariants}>
          <Card className="h-full">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Active Tickets</CardTitle>
                <CardDescription>Recent support requests</CardDescription>
              </div>
              <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard/ticketing')} className="text-primary-600 hover:bg-primary-50">
                View All
              </Button>
            </CardHeader>
            <CardContent>
              {tickets.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-slate-400">
                  <Ticket className="h-8 w-8 mb-2 opacity-50" />
                  <p className="text-sm">No active tickets</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {tickets.map((t) => (
                    <div key={t.id} className="flex items-center justify-between py-3 px-2 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded-xl transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-lg bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400">
                          <Ticket className="h-4 w-4" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-900 dark:text-white">{t.title}</p>
                          <p className="text-xs text-slate-500 dark:text-slate-400">{t.created_at ? formatDate(t.created_at) : 'Just now'}</p>
                        </div>
                      </div>
                      <Badge variant={t.status === 'resolved' ? 'success' : t.status === 'open' ? 'primary' : 'warning'} className="px-3 py-1 capitalize">
                        {t.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </motion.div>
  );
}