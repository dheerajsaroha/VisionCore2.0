import React, { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import { ProtectedRoute } from './components/ProtectedRoute';
import DashboardLayout from './layouts/DashboardLayout';
import { Spinner } from './components/ui/Spinner';
import { useTheme } from './hooks/useTheme';
import { useToast } from './components/ui/Toast';

const ScrollToTop = () => {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
};

// Lazy-loaded pages for code splitting
const LandingPage = lazy(() => import('./pages/LandingPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const SignupPage = lazy(() => import('./pages/SignupPage'));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage'));
const AccessDeniedPage = lazy(() => import('./pages/AccessDeniedPage'));
const Overview = lazy(() => import('./pages/Overview'));
const Attendance = lazy(() => import('./pages/Attendance'));
const UserManagement = lazy(() => import('./pages/UserManagement'));
const Reports = lazy(() => import('./pages/Reports'));
const Settings = lazy(() => import('./pages/Settings'));
const Ticketing = lazy(() => import('./pages/Ticketing'));
const Payroll = lazy(() => import('./pages/Payroll'));
const Reimbursements = lazy(() => import('./pages/Reimbursements'));
const PermissionManagement = lazy(() => import('./pages/PermissionManagement'));
const ScopeOwnershipPage = lazy(() => import('./pages/ScopeOwnershipPage'));
const ApprovalWorkflowPage = lazy(() => import('./pages/ApprovalWorkflowPage'));
const DynamicRoleManagementPage = lazy(() => import('./pages/DynamicRoleManagementPage'));
const LeaveManagementPage = lazy(() => import('./pages/LeaveManagementPage'));
const HRDashboardPage = lazy(() => import('./pages/HRDashboardPage'));
const PerformanceManagementPage = lazy(() => import('./pages/PerformanceManagementPage'));
const LearningDevelopmentPage = lazy(() => import('./pages/LearningDevelopmentPage'));
const SuccessionCareerPage = lazy(() => import('./pages/SuccessionCareerPage'));
const PolicyCenterPage = lazy(() => import('./pages/PolicyCenterPage'));
const AssetManagementPage = lazy(() => import('./pages/AssetManagementPage'));
const TenantAdminPage = lazy(() => import('./pages/TenantAdminPage'));
const EnterpriseIntegrationPage = lazy(() => import('./pages/EnterpriseIntegrationPage'));
const OperationsPage = lazy(() => import('./pages/OperationsPage'));

// Sprint 7 — AI Platform Pages
const AIStudioPage = lazy(() => import('./pages/AIStudioPage'));
const KnowledgeCenterPage = lazy(() => import('./pages/KnowledgeCenterPage'));
const AICopilotHubPage = lazy(() => import('./pages/AICopilotHubPage'));
const AIAnalyticsPage = lazy(() => import('./pages/AIAnalyticsPage'));
const PromptManagerPage = lazy(() => import('./pages/PromptManagerPage'));
const ModelManagerPage = lazy(() => import('./pages/ModelManagerPage'));
const AIUsageDashboardPage = lazy(() => import('./pages/AIUsageDashboardPage'));
const AIGovernanceDashboardPage = lazy(() => import('./pages/AIGovernanceDashboardPage'));

// Recruitment Pages
const OpenPositionsPage = lazy(() => import('./pages/OpenPositionsPage'));
const CandidatePipelinePage = lazy(() => import('./pages/CandidatePipelinePage'));

// Organization & Identity Domain Pages
const OrganizationDashboard = lazy(() => import('./pages/OrganizationDashboard'));
const OrganizationHierarchyTree = lazy(() => import('./pages/OrganizationHierarchyTree'));
const BusinessUnitsPage = lazy(() => import('./pages/BusinessUnitsPage'));
const BranchManagementPage = lazy(() => import('./pages/BranchManagementPage'));
const PositionManagementPage = lazy(() => import('./pages/PositionManagementPage'));
const IdentityDirectoryPage = lazy(() => import('./pages/IdentityDirectoryPage'));
const OrganizationSettingsPage = lazy(() => import('./pages/OrganizationSettingsPage'));

// Workforce Core Domain pages
const AttendanceDashboardPage = lazy(() => import('./pages/AttendanceDashboardPage'));
const AttendanceTimelinePage = lazy(() => import('./pages/AttendanceTimelinePage'));
const AttendanceDevicesPage = lazy(() => import('./pages/AttendanceDevicesPage'));
const ShiftCalendarPage = lazy(() => import('./pages/ShiftCalendarPage'));
const RosterPlannerPage = lazy(() => import('./pages/RosterPlannerPage'));
const LeaveCalendarPage = lazy(() => import('./pages/LeaveCalendarPage'));
const LeaveRequestsPage = lazy(() => import('./pages/LeaveRequestsPage'));
const WorkforcePlanningPage = lazy(() => import('./pages/WorkforcePlanningPage'));
const CapacityDashboardPage = lazy(() => import('./pages/CapacityDashboardPage'));
const AttendanceAnalyticsPage = lazy(() => import('./pages/AttendanceAnalyticsPage'));
const HolidayManagementPage = lazy(() => import('./pages/HolidayManagementPage'));

const LoadingFallback = () => (
  <div className="min-h-screen bg-gray-950 flex items-center justify-center">
    <Spinner size="xl" className="text-indigo-500" />
  </div>
);

const AppRoutes = () => {
  const toast = useToast();
  useEffect(() => {
    const handler = (e) => {
      toast?.({ message: e.detail || 'You do not have permission to access this resource.', type: 'error', duration: 5000 });
    };
    window.addEventListener('app:forbidden', handler);
    return () => window.removeEventListener('app:forbidden', handler);
  }, [toast]);

  const location = useLocation();

  return (
    <Routes location={location}>
      {/* Public Routes */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/403" element={<AccessDeniedPage />} />

      {/* Protected Dashboard Routes */}
      <Route path="/dashboard" element={
        <ProtectedRoute>
          <DashboardLayout><Overview /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/attendance" element={
        <ProtectedRoute requiredPermission="attendance.history">
          <DashboardLayout><Attendance /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/users" element={
        <ProtectedRoute requiredPermission="users.read">
          <DashboardLayout><UserManagement /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/reports" element={
        <ProtectedRoute requiredPermission="reports.attendance.export">
          <DashboardLayout><Reports /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/settings" element={
        <ProtectedRoute>
          <DashboardLayout><Settings /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/ticketing" element={
        <ProtectedRoute requiredPermission="tickets.read">
          <DashboardLayout><Ticketing /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/payroll" element={
        <ProtectedRoute requiredPermission="payroll.generate">
          <DashboardLayout><Payroll /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/reimbursements" element={
        <ProtectedRoute requiredPermission="reimbursements.create">
          <DashboardLayout><Reimbursements /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/leave" element={
        <ProtectedRoute requiredPermission="leave.view_self">
          <DashboardLayout><LeaveManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/workforce/attendance" element={<ProtectedRoute requiredPermission="attendance.history"><DashboardLayout><AttendanceDashboardPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/timeline" element={<ProtectedRoute requiredPermission="attendance.history"><DashboardLayout><AttendanceTimelinePage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/devices" element={<ProtectedRoute requiredPermission="platform.settings.manage"><DashboardLayout><AttendanceDevicesPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/shifts" element={<ProtectedRoute requiredPermission="shifts.read"><DashboardLayout><ShiftCalendarPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/rosters" element={<ProtectedRoute requiredPermission="shifts.read"><DashboardLayout><RosterPlannerPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/leave-calendar" element={<ProtectedRoute requiredPermission="leave.view_self"><DashboardLayout><LeaveCalendarPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/leave-requests" element={<ProtectedRoute requiredPermission="leave.view_self"><DashboardLayout><LeaveRequestsPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/planning" element={<ProtectedRoute requiredPermission="users.read"><DashboardLayout><WorkforcePlanningPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/capacity" element={<ProtectedRoute requiredPermission="users.read"><DashboardLayout><CapacityDashboardPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/analytics" element={<ProtectedRoute requiredPermission="reports.attendance.export"><DashboardLayout><AttendanceAnalyticsPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/holidays" element={<ProtectedRoute requiredPermission="org.settings.manage"><DashboardLayout><HolidayManagementPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/permissions" element={
        <ProtectedRoute requiredPermission="roles.view">
          <DashboardLayout><PermissionManagement /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/scope-ownership" element={
        <ProtectedRoute requiredPermission="platform.settings.manage">
          <DashboardLayout><ScopeOwnershipPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/approval-workflows" element={
        <ProtectedRoute requiredPermission="roles.view">
          <DashboardLayout><ApprovalWorkflowPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/dynamic-roles" element={
        <ProtectedRoute requiredPermission="roles.view">
          <DashboardLayout><DynamicRoleManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/hr" element={
        <ProtectedRoute requiredPermission="hcm.view">
          <DashboardLayout><HRDashboardPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/performance" element={
        <ProtectedRoute requiredPermission="performance.view">
          <DashboardLayout><PerformanceManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/learning" element={
        <ProtectedRoute requiredPermission="learning.view">
          <DashboardLayout><LearningDevelopmentPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/succession" element={
        <ProtectedRoute requiredPermission="succession.view">
          <DashboardLayout><SuccessionCareerPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/policies" element={
        <ProtectedRoute requiredPermission="policy.read">
          <DashboardLayout><PolicyCenterPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/assets" element={
        <ProtectedRoute requiredPermission="asset.read">
          <DashboardLayout><AssetManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/tenant-admin" element={
        <ProtectedRoute requiredPermission="admin.tenant.manage">
          <DashboardLayout><TenantAdminPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/enterprise" element={
        <ProtectedRoute requiredPermission="integration.manage">
          <DashboardLayout><EnterpriseIntegrationPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/operations" element={
        <ProtectedRoute requiredPermission="platform.settings.manage">
          <DashboardLayout><OperationsPage /></DashboardLayout>
        </ProtectedRoute>
      } />

      {/* Sprint 7 — AI Platform Routes */}
      <Route path="/dashboard/ai-studio" element={
        <ProtectedRoute requiredPermission="ai.studio.use">
          <DashboardLayout><AIStudioPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/knowledge-center" element={
        <ProtectedRoute requiredPermission="knowledge.read">
          <DashboardLayout><KnowledgeCenterPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/ai-copilot-hub" element={
        <ProtectedRoute requiredPermission="ai.copilot.use">
          <DashboardLayout><AICopilotHubPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/ai-analytics" element={
        <ProtectedRoute requiredPermission="ai.analytics.read">
          <DashboardLayout><AIAnalyticsPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/prompt-manager" element={
        <ProtectedRoute requiredPermission="ai.prompt.manage">
          <DashboardLayout><PromptManagerPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/model-manager" element={
        <ProtectedRoute requiredPermission="ai.model.manage">
          <DashboardLayout><ModelManagerPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/ai-usage" element={
        <ProtectedRoute requiredPermission="ai.analytics.read">
          <DashboardLayout><AIUsageDashboardPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/ai-governance" element={
        <ProtectedRoute requiredPermission="ai.governance.manage">
          <DashboardLayout><AIGovernanceDashboardPage /></DashboardLayout>
        </ProtectedRoute>
      } />

      {/* Recruitment Routes */}
      <Route path="/dashboard/open-positions" element={
        <ProtectedRoute requiredPermission="recruitment.view">
          <DashboardLayout><OpenPositionsPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/candidate-pipeline" element={
        <ProtectedRoute requiredPermission="recruitment.view">
          <DashboardLayout><CandidatePipelinePage /></DashboardLayout>
        </ProtectedRoute>
      } />

      {/* Organization & Identity Domain Routes */}
      <Route path="/dashboard/organization" element={
        <ProtectedRoute requiredPermission="org.view">
          <DashboardLayout><OrganizationDashboard /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/org-hierarchy" element={
        <ProtectedRoute requiredPermission="org.view">
          <DashboardLayout><OrganizationHierarchyTree /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/business-units" element={
        <ProtectedRoute requiredPermission="departments.read">
          <DashboardLayout><BusinessUnitsPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/branches" element={
        <ProtectedRoute requiredPermission="org.view">
          <DashboardLayout><BranchManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/positions" element={
        <ProtectedRoute requiredPermission="departments.read">
          <DashboardLayout><PositionManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/identity-directory" element={
        <ProtectedRoute requiredPermission="users.read">
          <DashboardLayout><IdentityDirectoryPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/org-settings" element={
        <ProtectedRoute requiredPermission="org.settings.view">
          <DashboardLayout><OrganizationSettingsPage /></DashboardLayout>
        </ProtectedRoute>
      } />

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

const App = () => {
  const { hydrate } = useAuthStore();
  // Initialize theme from localStorage — applies class to <html> element globally
  useTheme();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return (
    <Router>
      <ScrollToTop />
      <Suspense fallback={<LoadingFallback />}>
        <AppRoutes />
      </Suspense>
    </Router>
  );
};

export default App;
