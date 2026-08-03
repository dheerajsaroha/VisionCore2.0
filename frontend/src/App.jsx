import React, { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import { ProtectedRoute } from './components/ProtectedRoute';
import DashboardLayout from './layouts/DashboardLayout';
import { Spinner } from './components/ui/Spinner';

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
  const location = useLocation();

  return (
    <Routes location={location}>
      {/* Public Routes */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

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
        <ProtectedRoute requiredPermission="employee.read">
          <DashboardLayout><UserManagement /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/reports" element={
        <ProtectedRoute requiredPermission="report.generate">
          <DashboardLayout><Reports /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/settings" element={
        <ProtectedRoute requiredPermission="settings.read">
          <DashboardLayout><Settings /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/ticketing" element={
        <ProtectedRoute requiredPermission="support.ticket.read">
          <DashboardLayout><Ticketing /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/payroll" element={
        <ProtectedRoute requiredPermission="payroll.read">
          <DashboardLayout><Payroll /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/reimbursements" element={
        <ProtectedRoute requiredPermission="expense.submit">
          <DashboardLayout><Reimbursements /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/leave" element={
        <ProtectedRoute>
          <DashboardLayout><LeaveManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/workforce/attendance" element={<ProtectedRoute><DashboardLayout><AttendanceDashboardPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/timeline" element={<ProtectedRoute><DashboardLayout><AttendanceTimelinePage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/devices" element={<ProtectedRoute><DashboardLayout><AttendanceDevicesPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/shifts" element={<ProtectedRoute><DashboardLayout><ShiftCalendarPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/rosters" element={<ProtectedRoute><DashboardLayout><RosterPlannerPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/leave-calendar" element={<ProtectedRoute><DashboardLayout><LeaveCalendarPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/leave-requests" element={<ProtectedRoute><DashboardLayout><LeaveRequestsPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/planning" element={<ProtectedRoute><DashboardLayout><WorkforcePlanningPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/capacity" element={<ProtectedRoute><DashboardLayout><CapacityDashboardPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/analytics" element={<ProtectedRoute><DashboardLayout><AttendanceAnalyticsPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/workforce/holidays" element={<ProtectedRoute><DashboardLayout><HolidayManagementPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/dashboard/permissions" element={
        <ProtectedRoute requiredPermission="roles.view">
          <DashboardLayout><PermissionManagement /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/scope-ownership" element={
        <ProtectedRoute>
          <DashboardLayout><ScopeOwnershipPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/approval-workflows" element={
        <ProtectedRoute>
          <DashboardLayout><ApprovalWorkflowPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/dynamic-roles" element={
        <ProtectedRoute>
          <DashboardLayout><DynamicRoleManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/hr" element={
        <ProtectedRoute>
          <DashboardLayout><HRDashboardPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/performance" element={
        <ProtectedRoute>
          <DashboardLayout><PerformanceManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/learning" element={
        <ProtectedRoute>
          <DashboardLayout><LearningDevelopmentPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/succession" element={
        <ProtectedRoute>
          <DashboardLayout><SuccessionCareerPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/policies" element={
        <ProtectedRoute>
          <DashboardLayout><PolicyCenterPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/assets" element={
        <ProtectedRoute>
          <DashboardLayout><AssetManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/tenant-admin" element={
        <ProtectedRoute requiredPermission="admin.tenant.manage">
          <DashboardLayout><TenantAdminPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/enterprise" element={
        <ProtectedRoute>
          <DashboardLayout><EnterpriseIntegrationPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/operations" element={
        <ProtectedRoute>
          <DashboardLayout><OperationsPage /></DashboardLayout>
        </ProtectedRoute>
      } />

      {/* Sprint 7 — AI Platform Routes */}
      <Route path="/dashboard/ai-studio" element={
        <ProtectedRoute>
          <DashboardLayout><AIStudioPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/knowledge-center" element={
        <ProtectedRoute>
          <DashboardLayout><KnowledgeCenterPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/ai-copilot-hub" element={
        <ProtectedRoute>
          <DashboardLayout><AICopilotHubPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/ai-analytics" element={
        <ProtectedRoute>
          <DashboardLayout><AIAnalyticsPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/prompt-manager" element={
        <ProtectedRoute>
          <DashboardLayout><PromptManagerPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/model-manager" element={
        <ProtectedRoute>
          <DashboardLayout><ModelManagerPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/ai-usage" element={
        <ProtectedRoute>
          <DashboardLayout><AIUsageDashboardPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/ai-governance" element={
        <ProtectedRoute>
          <DashboardLayout><AIGovernanceDashboardPage /></DashboardLayout>
        </ProtectedRoute>
      } />

      {/* Recruitment Routes */}
      <Route path="/dashboard/open-positions" element={
        <ProtectedRoute>
          <DashboardLayout><OpenPositionsPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/candidate-pipeline" element={
        <ProtectedRoute>
          <DashboardLayout><CandidatePipelinePage /></DashboardLayout>
        </ProtectedRoute>
      } />

      {/* Organization & Identity Domain Routes */}
      <Route path="/dashboard/organization" element={
        <ProtectedRoute>
          <DashboardLayout><OrganizationDashboard /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/org-hierarchy" element={
        <ProtectedRoute>
          <DashboardLayout><OrganizationHierarchyTree /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/business-units" element={
        <ProtectedRoute>
          <DashboardLayout><BusinessUnitsPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/branches" element={
        <ProtectedRoute>
          <DashboardLayout><BranchManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/positions" element={
        <ProtectedRoute>
          <DashboardLayout><PositionManagementPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/identity-directory" element={
        <ProtectedRoute>
          <DashboardLayout><IdentityDirectoryPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/dashboard/org-settings" element={
        <ProtectedRoute>
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
