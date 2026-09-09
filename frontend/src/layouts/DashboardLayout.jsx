import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Clock,
  Users,
  BarChart3,
  Settings,
  Ticket,
  CreditCard,
  Receipt,
  Shield,
  Menu,
  LogOut,
  Bell,
  Search,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Package,
  Calendar,
  Trophy,
  Target,
  Briefcase,
  BookOpen,
  TrendingUp,
  BrainCircuit,
  Database,
  Bot,
  Sparkles,
  FileText,
  Cpu,
  Gauge,
  ShieldAlert,
  UserCheck,
  GitBranch,
  CheckSquare,
  Map,
  Globe,
  Activity,
  Building2,
  FileSpreadsheet,
  Layers,
  Sun,
  Moon,
  X,
  CheckCheck,
} from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { usePermission } from '../hooks/usePermission';
import { useTheme } from '../hooks/useTheme';
import { Avatar } from '../components/ui/Avatar';
import { cn } from '../lib/utils';
import { routeAccessForPath } from '../lib/routeAuthorization';
import { notificationService } from '../services/notificationService';


const navItems = [
  // Overview & Core
  { label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard', access: 'authenticated' },
  { label: 'Organization', icon: Building2, path: '/dashboard/organization', permission: 'org.view' },
  { label: 'Org Hierarchy', icon: GitBranch, path: '/dashboard/org-hierarchy', permission: 'org.view' },
  { label: 'Business Units', icon: Layers, path: '/dashboard/business-units', permission: 'departments.read' },
  { label: 'Branches', icon: Map, path: '/dashboard/branches', permission: 'org.view' },
  { label: 'Job Positions', icon: Briefcase, path: '/dashboard/positions', permission: 'departments.read' },
  { label: 'Identity Directory', icon: Users, path: '/dashboard/identity-directory', permission: 'users.read' },
  { label: 'Attendance', icon: Clock, path: '/dashboard/attendance', permission: 'attendance.history' },
  { label: 'Leave', icon: Calendar, path: '/dashboard/leave', access: 'authenticated' },
  { label: 'Workforce', icon: Activity, path: '/dashboard/workforce/attendance', permission: 'attendance.history' },
  { label: 'Shift Calendar', icon: Calendar, path: '/dashboard/workforce/shifts', permission: 'shifts.read' },
  { label: 'Roster Planner', icon: FileSpreadsheet, path: '/dashboard/workforce/rosters', permission: 'shifts.read' },
  { label: 'Workforce Planning', icon: Users, path: '/dashboard/workforce/planning', permission: 'users.read' },
  { label: 'Attendance Analytics', icon: BarChart3, path: '/dashboard/workforce/analytics', permission: 'reports.attendance.export' },
  { label: 'Users', icon: Users, path: '/dashboard/users', permission: 'users.read' },
  { label: 'HR Center', icon: UserCheck, path: '/dashboard/hr', permission: 'users.read' },

  // Operations
  { label: 'Ticketing', icon: Ticket, path: '/dashboard/ticketing', permission: 'tickets.read' },
  { label: 'Payroll', icon: CreditCard, path: '/dashboard/payroll', permission: 'payroll.generate' },
  { label: 'Reimbursements', icon: Receipt, path: '/dashboard/reimbursements', permission: 'reimbursements.create' },

  // HR Modules
  { label: 'Performance', icon: Trophy, path: '/dashboard/performance', permission: 'performance.cycle.read' },
  { label: 'L&D', icon: BookOpen, path: '/dashboard/learning', permission: 'learning.course.read' },
  { label: 'Succession', icon: TrendingUp, path: '/dashboard/succession', permission: 'succession.plan.read' },
  { label: 'Recruitment', icon: Briefcase, path: '/dashboard/open-positions', permission: 'recruitment.read' },

  // Governance & Policies
  { label: 'Policies', icon: Shield, path: '/dashboard/policies', permission: 'policy.read' },
  { label: 'Permissions', icon: ShieldCheck, path: '/dashboard/permissions', permission: 'roles.view' },
  { label: 'Dynamic Roles', icon: GitBranch, path: '/dashboard/dynamic-roles', permission: 'roles.view' },
  { label: 'Approval Workflows', icon: CheckSquare, path: '/dashboard/approval-workflows', permission: 'platform.settings.manage' },
  { label: 'Scope & Ownership', icon: Map, path: '/dashboard/scope-ownership', permission: 'platform.settings.manage' },

  // Assets & Enterprise
  { label: 'Assets', icon: Package, path: '/dashboard/assets', permission: 'asset.read' },
  { label: 'Enterprise', icon: Globe, path: '/dashboard/enterprise', permission: 'integration.manage' },
  { label: 'Operations', icon: Activity, path: '/dashboard/operations', permission: 'platform.settings.manage' },
  { label: 'Reports', icon: BarChart3, path: '/dashboard/reports', permission: 'reports.attendance.export' },

  // AI Platform
  { label: 'AI Studio', icon: BrainCircuit, path: '/dashboard/ai-studio', permission: 'ai.studio.use' },
  { label: 'Knowledge Center', icon: Database, path: '/dashboard/knowledge-center', permission: 'knowledge.read' },
  { label: 'AI Copilot Hub', icon: Bot, path: '/dashboard/ai-copilot-hub', permission: 'ai.copilot.use' },
  { label: 'AI Analytics', icon: Sparkles, path: '/dashboard/ai-analytics', permission: 'ai.analytics.read' },
  { label: 'Prompt Manager', icon: FileText, path: '/dashboard/prompt-manager', permission: 'ai.prompt.manage' },
  { label: 'Model Manager', icon: Cpu, path: '/dashboard/model-manager', permission: 'ai.model.manage' },
  { label: 'AI Usage', icon: Gauge, path: '/dashboard/ai-usage', permission: 'ai.analytics.read' },
  { label: 'AI Governance', icon: ShieldAlert, path: '/dashboard/ai-governance', permission: 'ai.governance.manage' },

  // Admin
  { label: 'Tenant Admin', icon: Building2, path: '/dashboard/tenant-admin', permission: 'admin.tenant.manage' },
  { label: 'Settings', icon: Settings, path: '/dashboard/settings', access: 'authenticated' },
];

const adminItems = [
  {
    label: 'System Settings',
    icon: Cpu,
    path: '/dashboard/settings',
    roles: ['SuperAdmin'],
    badge: 'Admin',
  },
  {
    label: 'Blockchain Settings',
    icon: ShieldCheck,
    path: '/dashboard/settings#blockchain',
    roles: ['SuperAdmin'],
    badge: 'Web3',
  },
];

const roleBadgeStyle = {
  SuperAdmin: 'bg-violet-500/15 text-violet-400 ring-1 ring-violet-500/30',
  Admin:      'bg-indigo-500/15  text-indigo-400  ring-1 ring-indigo-500/30',
  Manager:    'bg-sky-500/15     text-sky-400     ring-1 ring-sky-500/30',
  Employee:   'bg-gray-500/15    text-gray-400    ring-1 ring-gray-500/30',
};

const NavLink = ({ item, isActive, sidebarOpen }) => {
  const active = isActive(item.path);
  return (
    <Link
      to={item.path}
      title={!sidebarOpen ? item.label : undefined}
      className={cn(
        'relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group',
        active
          ? 'bg-indigo-500/10 text-indigo-300'
          : 'text-gray-400 hover:bg-gray-800/70 hover:text-gray-200'
      )}
    >
      {active && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-indigo-500 rounded-full" />
      )}
      <item.icon
        className={cn(
          'h-5 w-5 shrink-0 transition-colors duration-200',
          active ? 'text-indigo-400' : 'text-gray-500 group-hover:text-gray-300'
        )}
      />
      {sidebarOpen && (
        <span className="truncate">{item.label}</span>
      )}
      {sidebarOpen && item.badge && (
        <span className="ml-auto text-[10px] font-semibold px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-400">
          {item.badge}
        </span>
      )}
    </Link>
  );
};

const SidebarContent = ({ sidebarOpen, filteredNav, filteredAdmin, user, userRole, handleLogout, setSidebarOpen, navigate, isActive }) => (
  <div className="flex flex-col h-full">
    <div className="h-16 flex items-center px-4 border-b border-gray-800/80 shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shrink-0 shadow-lg shadow-indigo-500/30">
          <ShieldCheck className="h-5 w-5 text-white" />
        </div>
        {sidebarOpen && (
          <div className="min-w-0">
            <span className="text-base font-bold tracking-tight text-white block truncate">
              VisionCore
            </span>
            <span className="text-[10px] text-gray-500 font-medium">Attendance Platform</span>
          </div>
        )}
      </div>
    </div>

    <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-0.5 hide-scrollbar">
      {filteredNav.map((item) => (
        <NavLink key={item.path} item={item} isActive={isActive} sidebarOpen={sidebarOpen} />
      ))}

      {filteredAdmin.length > 0 && (
        <>
          {sidebarOpen && (
            <p className="px-3 pt-5 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-gray-600">
              Administration
            </p>
          )}
          {filteredAdmin.map((item) => (
            <NavLink key={item.path} item={item} isActive={isActive} sidebarOpen={sidebarOpen} />
          ))}
        </>
      )}
    </nav>

    <div className="p-3 border-t border-gray-800/80 space-y-1 shrink-0">
      <div
        className={cn(
          'flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-gray-800/70 transition-colors cursor-pointer',
          !sidebarOpen && 'justify-center'
        )}
        onClick={() => navigate('/dashboard/settings')}
      >
        <Avatar name={user?.full_name} size="sm" />
        {sidebarOpen && (
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold truncate text-white leading-tight">
              {user?.full_name || 'User'}
            </p>
            <span
              className={cn(
                'inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded-md mt-0.5',
                roleBadgeStyle[userRole] || roleBadgeStyle.Employee
              )}
            >
              {userRole}
            </span>
          </div>
        )}
      </div>

      <button
        onClick={handleLogout}
        title={!sidebarOpen ? 'Sign out' : undefined}
        className={cn(
          'flex items-center gap-3 px-3 py-2.5 w-full rounded-xl text-sm font-medium text-gray-400 hover:bg-red-500/10 hover:text-red-400 transition-colors',
          !sidebarOpen && 'justify-center'
        )}
      >
        <LogOut className="h-5 w-5 shrink-0" />
        {sidebarOpen && <span>Sign out</span>}
      </button>

      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="hidden lg:flex w-full items-center justify-center p-2 text-gray-600 hover:text-gray-400 hover:bg-gray-800 rounded-xl transition-colors mt-1"
        title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
      >
        {sidebarOpen
          ? <ChevronLeft className="h-4 w-4" />
          : <ChevronRight className="h-4 w-4" />}
      </button>
    </div>
  </div>
);

export default function DashboardLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  // ── Notifications ─────────────────────────────────────────────────
  const [notifPanelOpen, setNotifPanelOpen]   = useState(false);
  const [notifications,  setNotifications]    = useState([]);
  const [unreadCount,    setUnreadCount]      = useState(0);
  const notifRef = useRef(null);

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await notificationService.getNotifications({ limit: 20 });
      const data = res.data || res;
      setNotifications(data.notifications || []);
      setUnreadCount(data.unread_count ?? 0);
    } catch {
      /* silent */
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
    const id = setInterval(fetchNotifications, 30000); // poll every 30s
    return () => clearInterval(id);
  }, [fetchNotifications]);

  // Close panel on outside click
  useEffect(() => {
    const handler = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setNotifPanelOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleMarkAllRead = async () => {
    try {
      await notificationService.markAllRead();
      await fetchNotifications();
    } catch { /* silent */ }
  };

  const handleMarkRead = async (id) => {
    try {
      await notificationService.markRead(id);
      await fetchNotifications();
    } catch { /* silent */ }
  };

  // ── Theme ─────────────────────────────────────────────────────────
  const { theme, setTheme } = useTheme();
  const isDark = theme === 'dark';

  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { hasPermission } = usePermission();
  const userRole = user?.role?.name || 'Employee';


  const filteredNav = navItems.filter((item) => {
    const policy = routeAccessForPath(item.path);
    if (item.access === 'authenticated' || policy?.authenticated) return true;
    const requiredPermission = item.permission || policy?.permission;
    return Boolean(requiredPermission) && hasPermission(requiredPermission);
  });

  const filteredAdmin = adminItems.filter((item) => {
    return (!item.roles || item.roles.includes(userRole))
      && hasPermission('platform.settings.manage');
  });

  const isActive = (path) =>
    path === '/dashboard'
      ? location.pathname === '/dashboard'
      : location.pathname.startsWith(path);

  const prevPathRef = React.useRef(location.pathname);
  useEffect(() => {
    if (prevPathRef.current !== location.pathname) {
      prevPathRef.current = location.pathname;
      window.requestAnimationFrame(() => setMobileOpen(false));
    }
  }, [location.pathname]);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) setSidebarOpen(false);
      else setSidebarOpen(true);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex">
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-gray-950/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={cn(
          'fixed lg:sticky top-0 left-0 z-50 h-screen glass border-r border-gray-800/80 flex flex-col transition-all duration-300 ease-in-out',
          sidebarOpen ? 'w-64' : 'w-[72px]',
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        <SidebarContent
          sidebarOpen={sidebarOpen}
          filteredNav={filteredNav}
          filteredAdmin={filteredAdmin}
          user={user}
          userRole={userRole}
          handleLogout={handleLogout}
          setSidebarOpen={setSidebarOpen}
          navigate={navigate}
          isActive={isActive}
        />
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 glass border-b border-gray-800/80 px-4 lg:px-6 flex items-center justify-between sticky top-0 z-30">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-2 text-gray-500 hover:bg-gray-800 rounded-xl transition-colors"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>

            <nav className="hidden md:flex items-center text-sm" aria-label="Breadcrumb">
              <span className="text-gray-500">Dashboard</span>
              {location.pathname !== '/dashboard' && (
                <>
                  <span className="mx-2 text-gray-700">/</span>
                  <span className="font-semibold text-white capitalize">
                    {location.pathname.split('/').pop().replace(/-/g, ' ')}
                  </span>
                </>
              )}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <div className="hidden md:flex items-center bg-gray-800/70 border border-gray-700/50 rounded-xl px-3 py-2 transition-all focus-within:ring-2 focus-within:ring-indigo-500/50 focus-within:border-indigo-500/50">
              <Search className="h-4 w-4 text-gray-500 shrink-0" />
              <input
                type="text"
                placeholder="Search..."
                aria-label="Global search"
                className="bg-transparent border-none outline-none text-sm text-gray-200 placeholder:text-gray-600 ml-2 w-40"
              />
            </div>

            {/* Notification Bell */}
            <div className="relative" ref={notifRef}>
              <button
                id="notification-bell-btn"
                onClick={() => {
                  setNotifPanelOpen((v) => !v);
                  if (!notifPanelOpen) fetchNotifications();
                }}
                className="relative p-2.5 text-gray-500 hover:bg-gray-800 rounded-xl transition-colors"
                aria-label={`${unreadCount} unread notifications`}
              >
                <Bell className="h-5 w-5" />
                {unreadCount > 0 && (
                  <span className="absolute top-1.5 right-1.5 h-2 w-2 bg-red-500 rounded-full border-2 border-gray-950" />
                )}
              </button>

              {/* Dropdown Panel */}
              {notifPanelOpen && (
                <div
                  id="notification-panel"
                  className="absolute right-0 top-full mt-2 w-80 bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl z-50 overflow-hidden animate-fade-in"
                >
                  {/* Panel Header */}
                  <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
                    <div className="flex items-center gap-2">
                      <Bell className="h-4 w-4 text-indigo-400" />
                      <span className="text-sm font-semibold text-white">Notifications</span>
                      {unreadCount > 0 && (
                        <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                          {unreadCount}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      {unreadCount > 0 && (
                        <button
                          onClick={handleMarkAllRead}
                          title="Mark all as read"
                          className="p-1.5 rounded-lg text-gray-500 hover:text-indigo-400 hover:bg-gray-800 transition-colors"
                        >
                          <CheckCheck className="h-4 w-4" />
                        </button>
                      )}
                      <button
                        onClick={() => setNotifPanelOpen(false)}
                        className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  {/* Notification List */}
                  <div className="max-h-80 overflow-y-auto hide-scrollbar divide-y divide-gray-800/60">
                    {notifications.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-10 text-gray-600">
                        <Bell className="h-7 w-7 mb-2 opacity-25" />
                        <p className="text-sm">No notifications</p>
                      </div>
                    ) : (
                      notifications.map((n) => (
                        <div
                          key={n.id}
                          onClick={() => handleMarkRead(n.id)}
                          className={cn(
                            'px-4 py-3 hover:bg-gray-800/40 transition-colors cursor-pointer',
                            !n.is_read && 'bg-indigo-500/5 border-l-2 border-l-indigo-500'
                          )}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <p className={cn('text-sm leading-snug', n.is_read ? 'text-gray-400' : 'text-white font-medium')}>
                              {n.title}
                            </p>
                            {!n.is_read && (
                              <span className="shrink-0 h-2 w-2 rounded-full bg-indigo-500 mt-1" />
                            )}
                          </div>
                          <p className="text-xs text-gray-500 mt-1 line-clamp-2">{n.message}</p>
                          <p className="text-[10px] text-gray-600 mt-1">
                            {new Date(n.created_at).toLocaleString()}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Theme Toggle */}
            <button
              id="theme-toggle-btn"
              onClick={() => setTheme(isDark ? 'light' : 'dark')}
              className="p-2.5 text-gray-500 hover:bg-gray-800 rounded-xl transition-colors"
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              title={isDark ? 'Light Mode' : 'Dark Mode'}
            >
              {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>

            <button
              onClick={() => navigate('/dashboard/settings')}
              className="flex items-center gap-2 p-1 rounded-xl hover:bg-gray-800 transition-colors"
              aria-label="Go to settings"
            >
              <Avatar name={user?.full_name} size="sm" />
            </button>
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-8 overflow-y-auto hide-scrollbar">
          <div className="max-w-7xl mx-auto animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
