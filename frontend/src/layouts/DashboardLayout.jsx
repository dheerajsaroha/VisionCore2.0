import React, { useState, useEffect } from 'react';
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
<<<<<<< HEAD
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
=======
  Cpu,
>>>>>>> refs/remotes/origin/main
} from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { usePermission } from '../hooks/usePermission';
import { Avatar } from '../components/ui/Avatar';
import { cn } from '../lib/utils';

const navItems = [
<<<<<<< HEAD
  // Overview & Core
  { label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard', permission: '' },
  { label: 'Organization', icon: Building2, path: '/dashboard/organization', permission: '' },
  { label: 'Org Hierarchy', icon: GitBranch, path: '/dashboard/org-hierarchy', permission: '' },
  { label: 'Business Units', icon: Layers, path: '/dashboard/business-units', permission: '' },
  { label: 'Branches', icon: Map, path: '/dashboard/branches', permission: '' },
  { label: 'Job Positions', icon: Briefcase, path: '/dashboard/positions', permission: '' },
  { label: 'Identity Directory', icon: Users, path: '/dashboard/identity-directory', permission: '' },
  { label: 'Attendance', icon: Clock, path: '/dashboard/attendance', permission: 'attendance.history' },
  { label: 'Leave', icon: Calendar, path: '/dashboard/leave', permission: '' },
  { label: 'Workforce', icon: Activity, path: '/dashboard/workforce/attendance', permission: '' },
  { label: 'Shift Calendar', icon: Calendar, path: '/dashboard/workforce/shifts', permission: '' },
  { label: 'Roster Planner', icon: FileSpreadsheet, path: '/dashboard/workforce/rosters', permission: '' },
  { label: 'Workforce Planning', icon: Users, path: '/dashboard/workforce/planning', permission: '' },
  { label: 'Attendance Analytics', icon: BarChart3, path: '/dashboard/workforce/analytics', permission: '' },
  { label: 'Users', icon: Users, path: '/dashboard/users', permission: 'employee.read' },
  { label: 'HR Center', icon: UserCheck, path: '/dashboard/hr', permission: 'users.read' },

  // Operations
  { label: 'Ticketing', icon: Ticket, path: '/dashboard/ticketing', permission: 'support.ticket.read' },
  { label: 'Payroll', icon: CreditCard, path: '/dashboard/payroll', permission: 'payroll.read' },
  { label: 'Reimbursements', icon: Receipt, path: '/dashboard/reimbursements', permission: 'expense.submit' },

  // HR Modules
  { label: 'Performance', icon: Trophy, path: '/dashboard/performance', permission: 'performance.cycle.read' },
  { label: 'L&D', icon: BookOpen, path: '/dashboard/learning', permission: 'learning.course.read' },
  { label: 'Succession', icon: TrendingUp, path: '/dashboard/succession', permission: 'succession.plan.read' },
  { label: 'Recruitment', icon: Briefcase, path: '/dashboard/open-positions', permission: '' },

  // Governance & Policies
  { label: 'Policies', icon: Shield, path: '/dashboard/policies', permission: 'policy.read' },
  { label: 'Permissions', icon: ShieldCheck, path: '/dashboard/permissions', permission: 'roles.view' },
  { label: 'Dynamic Roles', icon: GitBranch, path: '/dashboard/dynamic-roles', permission: '' },
  { label: 'Approval Workflows', icon: CheckSquare, path: '/dashboard/approval-workflows', permission: '' },
  { label: 'Scope & Ownership', icon: Map, path: '/dashboard/scope-ownership', permission: '' },

  // Assets & Enterprise
  { label: 'Assets', icon: Package, path: '/dashboard/assets', permission: 'asset.read' },
  { label: 'Enterprise', icon: Globe, path: '/dashboard/enterprise', permission: '' },
  { label: 'Operations', icon: Activity, path: '/dashboard/operations', permission: '' },
  { label: 'Reports', icon: BarChart3, path: '/dashboard/reports', permission: 'report.generate' },

  // AI Platform
  { label: 'AI Studio', icon: BrainCircuit, path: '/dashboard/ai-studio', permission: '' },
  { label: 'Knowledge Center', icon: Database, path: '/dashboard/knowledge-center', permission: '' },
  { label: 'AI Copilot Hub', icon: Bot, path: '/dashboard/ai-copilot-hub', permission: '' },
  { label: 'AI Analytics', icon: Sparkles, path: '/dashboard/ai-analytics', permission: '' },
  { label: 'Prompt Manager', icon: FileText, path: '/dashboard/prompt-manager', permission: '' },
  { label: 'Model Manager', icon: Cpu, path: '/dashboard/model-manager', permission: '' },
  { label: 'AI Usage', icon: Gauge, path: '/dashboard/ai-usage', permission: '' },
  { label: 'AI Governance', icon: ShieldAlert, path: '/dashboard/ai-governance', permission: '' },

  // Admin
  { label: 'Tenant Admin', icon: Building2, path: '/dashboard/tenant-admin', permission: 'admin.tenant.manage' },
  { label: 'Settings', icon: Settings, path: '/dashboard/settings', permission: 'settings.read' },
=======
  {
    label: 'Overview',
    icon: LayoutDashboard,
    path: '/dashboard',
    roles: ['SuperAdmin', 'Admin', 'Manager', 'Employee'],
  },
  {
    label: 'Attendance',
    icon: Clock,
    path: '/dashboard/attendance',
    roles: ['SuperAdmin', 'Admin', 'Manager', 'Employee'],
  },
  {
    label: 'Users',
    icon: Users,
    path: '/dashboard/users',
    roles: ['SuperAdmin', 'Admin'],
  },
  {
    label: 'Reports',
    icon: BarChart3,
    path: '/dashboard/reports',
    roles: ['SuperAdmin', 'Admin', 'Manager'],
  },
  {
    label: 'Support',
    icon: Ticket,
    path: '/dashboard/ticketing',
    roles: ['SuperAdmin', 'Admin', 'Manager', 'Employee'],
  },
  {
    label: 'Payroll',
    icon: CreditCard,
    path: '/dashboard/payroll',
    roles: ['SuperAdmin', 'Admin'],
  },
  {
    label: 'Reimbursements',
    icon: Receipt,
    path: '/dashboard/reimbursements',
    roles: ['SuperAdmin', 'Admin', 'Manager', 'Employee'],
  },
>>>>>>> refs/remotes/origin/main
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


const bottomItems = [
  {
    label: 'Settings',
    icon: Settings,
    path: '/dashboard/settings',
    roles: ['SuperAdmin', 'Admin', 'Manager', 'Employee'],
  },
];

const roleBadgeStyle = {
  SuperAdmin: 'bg-violet-500/15 text-violet-400 ring-1 ring-violet-500/30',
  Admin:      'bg-indigo-500/15  text-indigo-400  ring-1 ring-indigo-500/30',
  Manager:    'bg-sky-500/15     text-sky-400     ring-1 ring-sky-500/30',
  Employee:   'bg-gray-500/15    text-gray-400    ring-1 ring-gray-500/30',
};

export default function DashboardLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notifications] = useState(3); // mock count
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { hasPermission } = usePermission();
  const userRole = user?.role?.name || 'Employee';

<<<<<<< HEAD
  // Permission-based filtering: show nav items based on permission (not hardcoded role)
  const filteredNav = navItems.filter((item) => {
    if (!item.permission) return true; // Items without specific permission requirement are accessible to all authenticated users
    return hasPermission(item.permission);
  });

  // Close mobile sidebar on route change — use useCallback ref to avoid state-in-effect lint
  const prevPathRef = React.useRef(location.pathname);
  useEffect(() => {
    if (prevPathRef.current !== location.pathname) {
      prevPathRef.current = location.pathname;
      // Defer state update to avoid cascading render warning
      window.requestAnimationFrame(() => setMobileOpen(false));
    }
  }, [location.pathname]);
=======
  const filteredNav   = navItems.filter((item) => item.roles.includes(userRole));
  const filteredAdmin = adminItems.filter((item) => item.roles.includes(userRole));

  useEffect(() => { setMobileOpen(false); }, [location.pathname]);
>>>>>>> refs/remotes/origin/main

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

  const isActive = (path) =>
    path === '/dashboard'
      ? location.pathname === '/dashboard'
      : location.pathname.startsWith(path);

  const NavLink = ({ item }) => {
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
        {/* Active left-border accent */}
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

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
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

      {/* Main Nav */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-0.5 hide-scrollbar">
        {filteredNav.map((item) => (
          <NavLink key={item.path} item={item} />
        ))}

        {/* SuperAdmin Section */}
        {filteredAdmin.length > 0 && (
          <>
            {sidebarOpen && (
              <p className="px-3 pt-5 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-gray-600">
                Administration
              </p>
            )}
            {filteredAdmin.map((item) => (
              <NavLink key={item.path} item={item} />
            ))}
          </>
        )}
      </nav>

      {/* Bottom: User + collapse */}
      <div className="p-3 border-t border-gray-800/80 space-y-1 shrink-0">
        {/* Profile row */}
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

        {/* Logout */}
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

        {/* Collapse toggle — desktop only */}
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

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-gray-950/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed lg:sticky top-0 left-0 z-50 h-screen glass border-r border-gray-800/80 flex flex-col transition-all duration-300 ease-in-out',
          sidebarOpen ? 'w-64' : 'w-[72px]',
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        <SidebarContent />
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <header className="h-16 glass border-b border-gray-800/80 px-4 lg:px-6 flex items-center justify-between sticky top-0 z-30">
          <div className="flex items-center gap-4">
            {/* Mobile hamburger */}
            <button
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-2 text-gray-500 hover:bg-gray-800 rounded-xl transition-colors"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>

            {/* Breadcrumb */}
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
            {/* Search */}
            <div className="hidden md:flex items-center bg-gray-800/70 border border-gray-700/50 rounded-xl px-3 py-2 transition-all focus-within:ring-2 focus-within:ring-indigo-500/50 focus-within:border-indigo-500/50">
              <Search className="h-4 w-4 text-gray-500 shrink-0" />
              <input
                type="text"
                placeholder="Search..."
                aria-label="Global search"
                className="bg-transparent border-none outline-none text-sm text-gray-200 placeholder:text-gray-600 ml-2 w-40"
              />
            </div>

            {/* Notifications */}
            <button
              className="relative p-2.5 text-gray-500 hover:bg-gray-800 rounded-xl transition-colors"
              aria-label={`${notifications} notifications`}
            >
              <Bell className="h-5 w-5" />
              {notifications > 0 && (
                <span className="absolute top-1.5 right-1.5 h-2 w-2 bg-red-500 rounded-full border-2 border-gray-950" />
              )}
            </button>

            {/* Avatar quick-menu */}
            <button
              onClick={() => navigate('/dashboard/settings')}
              className="flex items-center gap-2 p-1 rounded-xl hover:bg-gray-800 transition-colors"
              aria-label="Go to settings"
            >
              <Avatar name={user?.full_name} size="sm" />
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 lg:p-8 overflow-y-auto hide-scrollbar">
          <div className="max-w-7xl mx-auto animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
