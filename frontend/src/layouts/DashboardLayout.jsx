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
  FileSpreadsheet,
  Layers,
  Building2,
  Wallet,
} from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { usePermission } from '../hooks/usePermission';
import { useTheme } from '../hooks/useTheme';
import { Avatar } from '../components/ui/Avatar';
import { CommandPalette } from '../components/ui/CommandPalette';
import { cn } from '../lib/utils';
import { canAccess, resolvePolicy } from '../lib/accessControl';
import { notificationService } from '../services/notificationService';

// Categorized Navigation Groups for Application Shell
const NAV_GROUPS = [
  {
    group: 'CORE & IDENTITY',
    items: [
      { label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard' },
      { label: 'Organization', icon: Building2, path: '/dashboard/organization' },
      { label: 'Org Hierarchy', icon: GitBranch, path: '/dashboard/org-hierarchy' },
      { label: 'Business Units', icon: Layers, path: '/dashboard/business-units' },
      { label: 'Branches', icon: Map, path: '/dashboard/branches' },
      { label: 'Job Positions', icon: Briefcase, path: '/dashboard/positions' },
      { label: 'Identity Directory', icon: Users, path: '/dashboard/identity-directory' },
      { label: 'HR Center', icon: UserCheck, path: '/dashboard/hr' },
    ],
  },
  {
    group: 'WORKFORCE & BIOMETRICS',
    items: [
      { label: 'Biometric Attendance', icon: Clock, path: '/dashboard/attendance' },
      { label: 'Leave Requests', icon: Calendar, path: '/dashboard/leave' },
      { label: 'Workforce Core', icon: Activity, path: '/dashboard/workforce/attendance' },
      { label: 'Shift Calendar', icon: Calendar, path: '/dashboard/workforce/shifts' },
      { label: 'Roster Planner', icon: FileSpreadsheet, path: '/dashboard/workforce/rosters' },
      { label: 'Workforce Planning', icon: Users, path: '/dashboard/workforce/planning' },
      { label: 'Attendance Analytics', icon: BarChart3, path: '/dashboard/workforce/analytics' },
    ],
  },
  {
    group: 'HCM & GROWTH',
    items: [
      { label: 'Performance & OKRs', icon: Trophy, path: '/dashboard/performance' },
      { label: 'Learning & Dev', icon: BookOpen, path: '/dashboard/learning' },
      { label: 'Succession Planning', icon: TrendingUp, path: '/dashboard/succession' },
      { label: 'Recruitment', icon: Briefcase, path: '/dashboard/open-positions' },
    ],
  },
  {
    group: 'FINANCE & OPERATIONS',
    items: [
      { label: 'Payroll & Payslips', icon: CreditCard, path: '/dashboard/payroll' },
      { label: 'My Payslips', icon: Wallet, path: '/dashboard/my-payslips' },
      { label: 'Reimbursements', icon: Receipt, path: '/dashboard/reimbursements' },
      { label: 'Service Tickets', icon: Ticket, path: '/dashboard/ticketing' },
      { label: 'IT Assets', icon: Package, path: '/dashboard/assets' },
      { label: 'Operations', icon: Activity, path: '/dashboard/operations' },
      { label: 'Reports & Exports', icon: BarChart3, path: '/dashboard/reports' },
    ],
  },
  {
    group: 'GOVERNANCE & SECURITY',
    items: [
      { label: 'Policy Center', icon: Shield, path: '/dashboard/policies' },
      { label: '27-Role Permissions', icon: ShieldCheck, path: '/dashboard/permissions' },
      { label: 'Dynamic Roles', icon: GitBranch, path: '/dashboard/dynamic-roles' },
      { label: 'Approval Workflows', icon: CheckSquare, path: '/dashboard/approval-workflows' },
      { label: 'Scope Ownership', icon: Map, path: '/dashboard/scope-ownership' },
      { label: 'Integrations', icon: Globe, path: '/dashboard/enterprise' },
    ],
  },
  {
    group: 'AI PLATFORM',
    items: [
      { label: 'AI Studio', icon: BrainCircuit, path: '/dashboard/ai-studio' },
      { label: 'Knowledge Center', icon: Database, path: '/dashboard/knowledge-center' },
      { label: 'AI Copilot Hub', icon: Bot, path: '/dashboard/ai-copilot-hub' },
      { label: 'AI Analytics', icon: Sparkles, path: '/dashboard/ai-analytics' },
      { label: 'Prompt Manager', icon: FileText, path: '/dashboard/prompt-manager' },
      { label: 'Model Manager', icon: Cpu, path: '/dashboard/model-manager' },
      { label: 'AI Usage & Tokens', icon: Gauge, path: '/dashboard/ai-usage' },
      { label: 'AI Governance', icon: ShieldAlert, path: '/dashboard/ai-governance' },
    ],
  },
  {
    group: 'ADMINISTRATION',
    items: [
      { label: 'Tenant Admin', icon: Building2, path: '/dashboard/tenant-admin' },
      { label: 'Settings', icon: Settings, path: '/dashboard/settings' },
    ],
  },
];

const roleBadgeStyle = {
  SuperAdmin: 'bg-violet-500/20 text-violet-300 border border-violet-500/30',
  Admin: 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30',
  Manager: 'bg-sky-500/20 text-sky-300 border border-sky-500/30',
  Employee: 'bg-gray-500/20 text-gray-300 border border-gray-500/30',
};

const NavLink = ({ item, isActive, sidebarOpen }) => {
  const active = isActive(item.path);
  return (
    <Link
      to={item.path}
      title={!sidebarOpen ? item.label : undefined}
      className={cn(
        'relative flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-medium transition-all duration-150 group',
        active
          ? 'bg-indigo-600 text-white font-semibold shadow-md shadow-indigo-600/20'
          : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
      )}
    >
      <item.icon
        className={cn(
          'h-4 w-4 shrink-0 transition-colors duration-150',
          active ? 'text-white' : 'text-gray-400 group-hover:text-white'
        )}
      />
      {sidebarOpen && <span className="truncate">{item.label}</span>}
    </Link>
  );
};

export default function DashboardLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [, setMobileOpen] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);

  // ── Theme Engine Hook ─────────────────────────────────────────────
  const { theme, setTheme, availableThemes } = useTheme();

  // ── Notifications State ───────────────────────────────────────────
  const [notifPanelOpen, setNotifPanelOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const notifRef = useRef(null);

  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { hasPermission, hasFeature, featuresResolved } = usePermission();
  const userRole = user?.role?.name || 'Employee';

  // Keyboard shortcut listener for Ctrl+K or Cmd+K
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setCmdOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await notificationService.getNotifications({ limit: 20 });
      const data = res.data || res;
      setNotifications(data.notifications || []);
      setUnreadCount(data.unread_count ?? 0);
    } catch {
      /* silent fallback */
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Fetch remote notifications on mount and on the polling interval.
    fetchNotifications();
    const id = setInterval(fetchNotifications, 30000);
    return () => clearInterval(id);
  }, [fetchNotifications]);

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

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const isActivePath = (path) =>
    location.pathname === path ||
    (path === '/dashboard/identity-directory' && location.pathname === '/dashboard/users');

  // Generate Breadcrumbs
  const pathSegments = location.pathname.split('/').filter(Boolean);
  const breadcrumbs = pathSegments.map((segment, idx) => {
    const url = `/${pathSegments.slice(0, idx + 1).join('/')}`;
    const formatted = segment
      .replace(/-/g, ' ')
      .replace(/\b\w/g, (l) => l.toUpperCase());
    return { label: formatted, url };
  });

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans flex flex-col selection:bg-indigo-500 selection:text-white">
      {/* Global Command Palette Search Modal */}
      <CommandPalette isOpen={cmdOpen} onClose={() => setCmdOpen(false)} />

      <div className="flex flex-1 overflow-hidden">
        {/* Desktop Sidebar */}
        <aside
          className={cn(
            'hidden lg:flex flex-col border-r border-gray-800 bg-gray-950 transition-all duration-300 z-30 shrink-0',
            sidebarOpen ? 'w-64' : 'w-20'
          )}
        >
          {/* Logo Header */}
          <div className="h-16 flex items-center justify-between px-4 border-b border-gray-800 shrink-0">
            <Link to="/dashboard" className="flex items-center gap-3 min-w-0">
              <div className="h-9 w-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white shrink-0 shadow-lg shadow-indigo-600/30">
                <ShieldCheck className="h-5 w-5" />
              </div>
              {sidebarOpen && (
                <div className="min-w-0">
                  <span className="text-base font-extrabold text-white block truncate tracking-tight">
                    VisionCore
                  </span>
                  <span className="text-[10px] text-indigo-400 font-mono font-medium block">v2.4 Enterprise</span>
                </div>
              )}
            </Link>
            {sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(false)}
                className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
                title="Collapse Sidebar"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Categorized Nav Groups */}
          <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-6 hide-scrollbar">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="w-full flex items-center justify-center p-2 rounded-xl text-gray-400 hover:text-white hover:bg-gray-800 mb-4"
                title="Expand Sidebar"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            )}

            {NAV_GROUPS.map((group) => {
              // Hides on BOTH dimensions: the RBAC permission and the plan
              // feature. Either one missing removes the entry outright, so a
              // user is never shown a module they cannot open. Re-evaluating on
              // every render means an admin's grant appears as soon as the
              // permission store refreshes, with no re-login.
              //
              // Until the plan's feature list is known the sidebar waits rather
              // than showing everything and then hiding it, which flashed a full
              // sidebar on every load.
              if (!featuresResolved) return null;

              const accessibleItems = group.items.filter((item) => {
                const policy = resolvePolicy(item.path);
                return canAccess(policy, {
                  hasPermission,
                  hasFeature,
                  isAuthenticated: true,
                }).allowed;
              });

              if (accessibleItems.length === 0) return null;

              return (
                <div key={group.group} className="space-y-1">
                  {sidebarOpen && (
                    <div className="px-3 text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5">
                      {group.group}
                    </div>
                  )}
                  {accessibleItems.map((item) => (
                    <NavLink
                      key={item.path + item.label}
                      item={item}
                      isActive={isActivePath}
                      sidebarOpen={sidebarOpen}
                    />
                  ))}
                </div>
              );
            })}
          </nav>

          {/* Footer User Profile & Collapse */}
          <div className="p-3 border-t border-gray-800 space-y-1 shrink-0 bg-gray-950">
            <div
              onClick={() => navigate('/dashboard/settings')}
              className={cn(
                'flex items-center gap-3 p-2 rounded-xl hover:bg-gray-900 transition-colors cursor-pointer',
                !sidebarOpen && 'justify-center'
              )}
            >
              <Avatar name={user?.full_name} size="sm" />
              {sidebarOpen && (
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-white truncate leading-tight">
                    {user?.full_name || 'Enterprise User'}
                  </p>
                  <span className={cn('inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded-md mt-0.5', roleBadgeStyle[userRole] || roleBadgeStyle.Employee)}>
                    {userRole}
                  </span>
                </div>
              )}
            </div>

            <button
              onClick={handleLogout}
              className={cn(
                'flex items-center gap-3 px-3 py-2 w-full rounded-xl text-xs font-semibold text-gray-400 hover:bg-red-500/10 hover:text-red-400 transition-colors',
                !sidebarOpen && 'justify-center'
              )}
            >
              <LogOut className="h-4 w-4 shrink-0" />
              {sidebarOpen && <span>Sign out</span>}
            </button>
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Top Bar Header */}
          <header className="h-16 border-b border-gray-800 bg-gray-950/90 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between gap-4 z-20 shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              {/* Mobile Sidebar Toggle */}
              <button
                onClick={() => setMobileOpen(true)}
                className="lg:hidden p-2 text-gray-400 hover:text-white"
                aria-label="Open navigation"
              >
                <Menu className="h-5 w-5" />
              </button>

              {/* Breadcrumbs */}
              <nav aria-label="Breadcrumb" className="hidden sm:flex items-center gap-1.5 text-xs text-gray-400 overflow-hidden">
                {breadcrumbs.map((b, idx) => (
                  <React.Fragment key={b.url}>
                    {idx > 0 && <ChevronRight className="h-3.5 w-3.5 text-gray-400 shrink-0" />}
                    <Link
                      to={b.url}
                      className={cn(
                        'hover:text-white transition-colors truncate',
                        idx === breadcrumbs.length - 1 ? 'font-semibold text-white' : 'text-gray-400'
                      )}
                    >
                      {b.label}
                    </Link>
                  </React.Fragment>
                ))}
              </nav>
            </div>

            {/* Topbar Actions */}
            <div className="flex items-center gap-3">
              {/* Quick Command Palette Button */}
              <button
                onClick={() => setCmdOpen(true)}
                className="hidden md:flex items-center gap-3 px-3.5 py-1.5 rounded-xl border border-gray-800 bg-gray-900/80 text-xs font-medium text-gray-400 hover:text-white hover:border-gray-700 transition-all"
              >
                <Search className="h-3.5 w-3.5 text-indigo-400" />
                <span>Search pages & commands...</span>
                <kbd className="px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 font-mono text-[10px] text-gray-400">
                  Ctrl+K
                </kbd>
              </button>

              {/* Tenant / Organization Switcher Indicator */}
              <div className="hidden xl:flex items-center gap-2 px-3 py-1 rounded-xl bg-gray-900 border border-gray-800 text-xs text-gray-300">
                <Building2 className="h-3.5 w-3.5 text-indigo-400" />
                <span className="font-semibold text-white">Global Org Tenant</span>
              </div>

              {/* Multi-Theme Selector */}
              <div className="flex items-center gap-1 p-1 rounded-xl border border-gray-800 bg-gray-900">
                {availableThemes.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setTheme(t.id)}
                    className={cn(
                      'p-1.5 rounded-lg text-xs transition-all',
                      theme === t.id ? 'bg-indigo-600 text-white shadow-sm' : 'text-gray-400 hover:text-white'
                    )}
                    title={`Theme: ${t.label}`}
                  >
                    <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: t.color }} />
                  </button>
                ))}
              </div>

              {/* Notification Panel Trigger */}
              <div className="relative" ref={notifRef}>
                <button
                  onClick={() => setNotifPanelOpen(!notifPanelOpen)}
                  className="p-2 rounded-xl border border-gray-800 bg-gray-900 text-gray-400 hover:text-white transition-colors relative"
                  aria-label="Notifications"
                >
                  <Bell className="h-4 w-4" />
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 h-4 min-w-[16px] px-1 rounded-full bg-indigo-600 text-white text-[10px] font-bold flex items-center justify-center">
                      {unreadCount}
                    </span>
                  )}
                </button>

                {/* Notifications Drawer */}
                {notifPanelOpen && (
                  <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl bg-gray-900 border border-gray-800 shadow-2xl p-4 z-50 text-xs">
                    <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-3">
                      <div className="font-bold text-white text-sm flex items-center gap-2">
                        <Bell className="h-4 w-4 text-indigo-400" /> Notifications
                      </div>
                      {unreadCount > 0 && (
                        <button
                          onClick={handleMarkAllRead}
                          className="text-[11px] text-indigo-400 hover:text-indigo-300 font-semibold"
                        >
                          Mark all read
                        </button>
                      )}
                    </div>

                    <div className="max-h-72 overflow-y-auto space-y-2 hide-scrollbar">
                      {notifications.length === 0 ? (
                        <div className="py-6 text-center text-gray-500">No new notifications</div>
                      ) : (
                        notifications.map((n) => (
                          <div
                            key={n.id}
                            className={cn(
                              'p-3 rounded-xl border transition-colors',
                              n.read ? 'bg-gray-950/40 border-gray-800/50 text-gray-400' : 'bg-indigo-950/20 border-indigo-500/30 text-white'
                            )}
                          >
                            <div className="font-semibold text-xs">{n.title || 'System Notification'}</div>
                            <div className="text-[11px] text-gray-300 mt-0.5">{n.message}</div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </header>

          {/* Main Page Viewport */}
          <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-gray-950">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
