/**
 * Overview.jsx
 * Phase 4 — Data-Driven Role-Aware Enterprise Command Center.
 *
 * Visual hierarchy:
 *   DashboardHeader (Topbar / Context)
 *     ↓
 *   KPIGrid (Critical Role-Aware KPIs)
 *     ↓
 *   Primary Workforce Analytics (WorkforceOverview + AttendanceOverview)
 *     ↓
 *   Action Centers (ApprovalCenter + AlertsPanel)
 *     ↓
 *   Schedules & Pulse (LeaveOverview + ActivityFeed)
 *     ↓
 *   Enterprise Analytics (AnalyticsSection)
 *     ↓
 *   AI Intelligence (AIInsightsWidget)
 */
import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AlertCircle } from 'lucide-react';

import { useAuthStore } from '../store/authStore';
import { usePermission } from '../hooks/usePermission';
import { canApproveWorkflows } from '../lib/accessControl';
import { dashboardService } from '../services/dashboardService';
import { departmentService } from '../services/departmentService';

import { 
  DashboardHeader, KPIGrid, WorkforceOverview, 
  AttendanceOverview, LeaveOverview, ApprovalCenter, 
  AlertsPanel, ActivityFeed, AnalyticsSection, AIInsightsWidget 
} from '../components/dashboard';

import { EmployeeDetailModal } from '../components/EmployeeDetailModal';
import { OrganizationDetailModal } from '../components/OrganizationDetailModal';
import { Spinner } from '../components/ui/Spinner';
import { Button } from '../components/ui/Button';

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
};

export default function Overview() {
  const { user } = useAuthStore();
  const { hasPermission, hasFeature } = usePermission();
  // Resolved once per render so the data load below can skip endpoints the
  // caller is not entitled to, instead of firing them and absorbing the 403.
  const canReadDepartments = hasPermission('departments.read');
  // Mirrors the backend's role-name predicate on the approval action; see
  // canApproveWorkflows for why this is not a permission check.
  const canApprove = canApproveWorkflows(user?.role?.name || user?.role);
  const canUseCopilot = hasFeature('ai_chat');
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Command Center state
  const [stats, setStats] = useState(null);
  const [workforceData, setWorkforceData] = useState(null);
  const [attendanceData, setAttendanceData] = useState(null);
  const [leaveData, setLeaveData] = useState(null);
  const [approvals, setApprovals] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [activities, setActivities] = useState([]);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [aiInsights, setAiInsights] = useState([]);
  const [departments, setDepartments] = useState([]);

  // Modals & feedback
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [showOrgModal, setShowOrgModal] = useState(false);
  const [toast, setToast] = useState(null);

  const fetchRef = useRef(false);
  const roleName = (user?.role?.name || user?.role || '').toLowerCase();

  const fetchDashboardData = useCallback(async () => {
    try {
      setError(null);
      const [
        overviewRes,
        workforceRes,
        attendanceRes,
        leaveRes,
        approvalsRes,
        alertsRes,
        activityRes,
        analyticsRes,
        aiRes,
        deptRes,
      ] = await Promise.allSettled([
        dashboardService.getOverview(),
        dashboardService.getWorkforceBreakdown(),
        dashboardService.getAttendanceStats(),
        dashboardService.getLeaveOverview(),
        dashboardService.getPendingApprovals(),
        dashboardService.getAlerts(),
        dashboardService.getActivityFeed('all', 15),
        dashboardService.getAnalytics(),
        dashboardService.getAIInsights(),
        // The departments endpoint requires `departments.read`, which most
        // employees do not hold. Firing it unconditionally put a red
        // "Missing required permission" toast on the dashboard for every
        // ordinary user, on every load and every refresh. Ask first, and mark
        // the request as an expected denial so the interceptor stays quiet.
        canReadDepartments
          ? departmentService.getDepartments({ suppressForbiddenToast: true })
          : Promise.resolve({ data: [] }),
      ]);

      if (overviewRes.status === 'fulfilled' && overviewRes.value) {
        setStats(overviewRes.value.stats || overviewRes.value);
      }
      if (workforceRes.status === 'fulfilled' && workforceRes.value) {
        setWorkforceData(workforceRes.value);
      }
      if (attendanceRes.status === 'fulfilled' && attendanceRes.value) {
        setAttendanceData(attendanceRes.value);
      }
      if (leaveRes.status === 'fulfilled' && leaveRes.value) {
        setLeaveData(leaveRes.value);
      }
      if (approvalsRes.status === 'fulfilled' && Array.isArray(approvalsRes.value)) {
        setApprovals(approvalsRes.value);
      }
      if (alertsRes.status === 'fulfilled' && Array.isArray(alertsRes.value)) {
        setAlerts(alertsRes.value);
      }
      if (activityRes.status === 'fulfilled' && Array.isArray(activityRes.value)) {
        setActivities(activityRes.value);
      }
      if (analyticsRes.status === 'fulfilled' && analyticsRes.value) {
        setAnalyticsData(analyticsRes.value);
      }
      if (aiRes.status === 'fulfilled' && Array.isArray(aiRes.value)) {
        setAiInsights(aiRes.value);
      }
      if (deptRes.status === 'fulfilled' && deptRes.value) {
        const dData = deptRes.value.data || deptRes.value;
        setDepartments(Array.isArray(dData) ? dData : []);
      }
    } catch (err) {
      console.error('Failed to load command center data:', err);
      setError('Could not load some dashboard metrics. Retrying...');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
    // `canReadDepartments` is a dependency because the departments call is
    // skipped without it. Leaving it out would capture the value from first
    // render, so a permission granted later would never take effect here.
  }, [canReadDepartments]);

  useEffect(() => {
    if (fetchRef.current) return;
    fetchRef.current = true;
    fetchDashboardData();
    return () => {
      fetchRef.current = false;
    };
  }, [fetchDashboardData]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchDashboardData();
  };

  const handleDepartmentFilter = async (deptId) => {
    try {
      const data = await dashboardService.getWorkforceBreakdown(deptId);
      if (data) {
        setWorkforceData(data);
      }
    } catch (err) {
      console.warn('Department filter failed:', err);
    }
  };

  const handleActivityFilter = async (filterType) => {
    try {
      const acts = await dashboardService.getActivityFeed(filterType, 15);
      if (Array.isArray(acts)) {
        setActivities(acts);
      }
    } catch (err) {
      console.warn('Activity filter failed:', err);
    }
  };

  const handleApprovalAction = async (item, action) => {
    try {
      const result = await dashboardService.processApprovalAction(
        item.item_type || 'workflow',
        item.raw_id,
        action
      );
      // Remove from pending list
      setApprovals((prev) => prev.filter((i) => i.id !== item.id));
      setToast({
        type: 'success',
        text: result?.message || `Request successfully ${action}d.`,
      });
      // Refresh overview counts
      dashboardService.getOverview().then((res) => {
        if (res?.stats) setStats(res.stats);
      });
    } catch (err) {
      console.error('Approval action error:', err);
      setToast({
        type: 'error',
        text: err?.response?.data?.detail || `Failed to ${action} request.`,
      });
    }
  };

  const handleCheckInNow = () => {
    navigate('/dashboard/attendance');
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[550px]">
        <Spinner size="xl" className="text-indigo-500 mb-3" />
        <p className="text-sm font-semibold text-slate-200">Loading Command Center Intelligence...</p>
        <p className="text-xs text-slate-500 mt-1">Aggregating live PostgreSQL workforce metrics</p>
      </div>
    );
  }

  return (
    <>
      <motion.div
        className="space-y-8 pb-12"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Error Banner with Retry */}
        {error && (
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
            <Button size="xs" variant="outline" onClick={handleRefresh}>
              Retry
            </Button>
          </div>
        )}

        {/* 1. Topbar Welcome / Role Header */}
        <motion.div variants={itemVariants}>
          <DashboardHeader
            user={user}
            roleName={roleName}
            onRefresh={handleRefresh}
            refreshing={refreshing}
            onCheckIn={handleCheckInNow}
          />
        </motion.div>

        {/* 2. Executive Role-Aware KPI Cards Grid */}
        <motion.div variants={itemVariants}>
          <KPIGrid
            stats={stats}
            roleName={roleName}
            loading={loading}
          />
        </motion.div>

        {/* 3. Primary Workforce Architecture & Distribution */}
        <motion.div variants={itemVariants}>
          <WorkforceOverview
            data={workforceData}
            departments={departments}
            onDepartmentChange={handleDepartmentFilter}
            loading={loading}
          />
        </motion.div>

        {/* 4. Real-Time Attendance Intelligence & Live Stream */}
        <motion.div variants={itemVariants}>
          <AttendanceOverview
            logs={attendanceData?.recentLogs || []}
            chartData={attendanceData?.trends || []}
            departmentData={attendanceData?.departmentAttendance || []}
            stats={attendanceData?.today || stats}
            loading={loading}
            onSelectUser={(userId) => setSelectedUserId(userId)}
          />
        </motion.div>

        {/* 5. Approvals Center + Workforce Alerts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <motion.div variants={itemVariants}>
            <ApprovalCenter
              items={approvals}
              canAction={canApprove}
              onApprove={(item) => handleApprovalAction(item, 'approve')}
              onReject={(item) => handleApprovalAction(item, 'reject')}
              loading={loading}
            />
          </motion.div>

          <motion.div variants={itemVariants}>
            <AlertsPanel
              alerts={alerts}
              loading={loading}
            />
          </motion.div>
        </div>

        {/* 6. Leave Overview + Unified Activity Feed Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <motion.div variants={itemVariants}>
            <LeaveOverview
              leaveSummary={leaveData}
              userRole={roleName}
              loading={loading}
            />
          </motion.div>

          <motion.div variants={itemVariants}>
            <ActivityFeed
              activities={activities}
              onFilterChange={handleActivityFilter}
              loading={loading}
            />
          </motion.div>
        </div>

        {/* 7. Enterprise Multi-Dimensional Analytics */}
        <motion.div variants={itemVariants}>
          <AnalyticsSection
            data={analyticsData}
            loading={loading}
          />
        </motion.div>

        {/* 8. VisionCore Permission-Guarded AI Insights */}
        {canUseCopilot && (
        <motion.div variants={itemVariants}>
          <AIInsightsWidget
            roleName={roleName}
            insights={aiInsights}
            loading={loading}
          />
        </motion.div>
        )}
      </motion.div>

      {/* Floating Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50">
          <div
            className={`p-4 rounded-2xl border text-xs font-semibold shadow-2xl flex items-center justify-between gap-3 ${
              toast.type === 'success'
                ? 'bg-emerald-950/90 text-emerald-200 border-emerald-500/30'
                : 'bg-rose-950/90 text-rose-200 border-rose-500/30'
            }`}
          >
            <span>{toast.text}</span>
            <button
              onClick={() => setToast(null)}
              className="text-slate-400 hover:text-white ml-2 text-sm leading-none"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Modals */}
      <EmployeeDetailModal
        userId={selectedUserId}
        isOpen={!!selectedUserId}
        onClose={() => setSelectedUserId(null)}
      />
      <OrganizationDetailModal
        isOpen={showOrgModal}
        onClose={() => setShowOrgModal(false)}
      />
    </>
  );
}
