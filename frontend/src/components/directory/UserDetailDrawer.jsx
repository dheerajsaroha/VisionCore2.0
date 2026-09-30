/**
 * UserDetailDrawer.jsx
 * Enterprise User Profile & Identity Dossier Drawer.
 * Multi-tab comprehensive inspection: Identity, Organization, Access & RBAC, Biometrics & Timeline.
 * Strict Phase 2 theme engine compliance.
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  User,
  Mail,
  Phone,
  Building2,
  Briefcase,
  Shield,
  Key,
  Fingerprint,
  History,
  MapPin,
  Clock,
  Calendar,
  Laptop,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Edit3,
  UserX,
  UserCheck,
  Trash2,
  ArrowUpRight,
  Trophy,
  CreditCard,
  Activity,
} from 'lucide-react';
import { Avatar } from '../ui/Avatar';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/Tabs';
import { UserStatusBadge, RoleBadge, EmploymentTypeBadge } from './UserStatusBadge';
import { formatDate } from '../../lib/utils';
import userService from '../../services/userService';

export function UserDetailDrawer({
  user,
  isOpen,
  onClose,
  currentUserId,
  canEdit = false,
  canDelete = false,
  canAssignRole = false,
  onEdit,
  onAssignRole,
  onActivate,
  onSuspend,
  onEnroll,
  onDelete,
}) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('identity');
  const [permissions, setPermissions] = useState([]);
  const [trustedDevices, setTrustedDevices] = useState([]);
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [loadingDetails, setLoadingDetails] = useState(false);

  const isSelf = currentUserId === user?.id;
  // Keep biometric controls in sync with the enrollment endpoint: a user can
  // enroll themself, while enrollment for another identity needs users.update.
  const canEnroll = Boolean(onEnroll) && (isSelf || canEdit);

  useEffect(() => {
    if (!isOpen || !user?.id) return;

    let isMounted = true;
    const fetchAuxiliaryData = async () => {
      setLoadingDetails(true);
      try {
        const [permsRes, devicesRes, timelineRes] = await Promise.allSettled([
          userService.getUserPermissions(user.id),
          userService.getTrustedDevices(user.id),
          userService.getIdentityTimeline(user.id),
        ]);

        if (!isMounted) return;

        if (permsRes.status === 'fulfilled') {
          setPermissions(permsRes.value.data?.permissions || permsRes.value.data || []);
        } else {
          setPermissions([]);
        }

        if (devicesRes.status === 'fulfilled') {
          setTrustedDevices(devicesRes.value.data || []);
        } else {
          setTrustedDevices([]);
        }

        if (timelineRes.status === 'fulfilled') {
          setTimelineEvents(timelineRes.value.data || []);
        } else {
          setTimelineEvents([]);
        }
      } catch (e) {
        console.error('Failed to load user details:', e);
      } finally {
        if (isMounted) setLoadingDetails(false);
      }
    };

    fetchAuxiliaryData();
    return () => {
      isMounted = false;
    };
  }, [isOpen, user?.id]);

  if (!isOpen || !user) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 overflow-hidden">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 bg-gray-950/70 backdrop-blur-sm transition-opacity"
        />

        {/* Drawer Panel */}
        <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 240 }}
            className="w-screen max-w-xl glass bg-gray-900/95 border-l border-gray-800 shadow-2xl flex flex-col backdrop-blur-xl"
          >
            {/* Header */}
            <div className="p-6 border-b border-gray-800/80 flex items-start justify-between gap-4">
              <div className="flex items-center gap-4">
                <Avatar
                  name={user.full_name}
                  size="lg"
                  className="ring-2 ring-indigo-500/30 shadow-lg"
                />
                <div>
                  <h2 className="text-lg font-bold text-gray-100 flex items-center gap-2">
                    <span>{user.full_name}</span>
                    <RoleBadge role={user.role} />
                  </h2>
                  <p className="text-xs text-gray-400 mt-0.5">{user.email}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <UserStatusBadge
                      isActive={Boolean(user.is_active)}
                      hasFaceEnrolled={Boolean(user.has_face_enrolled)}
                    />
                    <EmploymentTypeBadge type={user.employment_type} />
                  </div>
                </div>
              </div>

              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition-colors"
                aria-label="Close dossier"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Quick Actions Bar */}
            <div className="px-6 py-2.5 bg-gray-950/40 border-b border-gray-800/80 flex items-center justify-between gap-2 overflow-x-auto">
              <div className="flex items-center gap-2">
                {canEdit && onEdit && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => { onEdit(user); }}
                    className="text-xs text-gray-300 hover:text-white"
                  >
                    <Edit3 className="h-3.5 w-3.5 mr-1 text-sky-400" />
                    Edit
                  </Button>
                )}
                {canAssignRole && onAssignRole && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => { onAssignRole(user); }}
                    className="text-xs text-gray-300 hover:text-white"
                  >
                    <Shield className="h-3.5 w-3.5 mr-1 text-purple-400" />
                    Role
                  </Button>
                )}
                {canEnroll && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => { onEnroll(user); }}
                    className="text-xs text-gray-300 hover:text-white"
                  >
                    <Fingerprint className="h-3.5 w-3.5 mr-1 text-cyan-400" />
                    Biometrics
                  </Button>
                )}
              </div>

              <div className="flex items-center gap-2">
                {canEdit && !isSelf && (
                  user.is_active ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => { onSuspend(user); }}
                      className="text-xs text-amber-400 hover:bg-amber-500/10"
                    >
                      <UserX className="h-3.5 w-3.5 mr-1" />
                      Suspend
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => { onActivate(user); }}
                      className="text-xs text-emerald-400 hover:bg-emerald-500/10"
                    >
                      <UserCheck className="h-3.5 w-3.5 mr-1" />
                      Activate
                    </Button>
                  )
                )}
              </div>
            </div>

            {/* Content Tabs */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="grid grid-cols-4 bg-gray-950/60 p-1 border border-gray-800 rounded-xl">
                  <TabsTrigger value="identity" className="text-xs">Identity</TabsTrigger>
                  <TabsTrigger value="org" className="text-xs">Organization</TabsTrigger>
                  <TabsTrigger value="access" className="text-xs">Access & RBAC</TabsTrigger>
                  <TabsTrigger value="timeline" className="text-xs">Audit Trail</TabsTrigger>
                </TabsList>

                {/* Tab 1: Identity Information */}
                <TabsContent value="identity" className="space-y-4 pt-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <User className="h-3 w-3 text-indigo-400" /> Full Name
                      </span>
                      <p className="text-sm font-semibold text-gray-100 mt-1">{user.full_name}</p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <User className="h-3 w-3 text-indigo-400" /> Employee ID
                      </span>
                      <p className="text-sm font-mono font-semibold text-gray-100 mt-1">
                        {user.employee_id || `EMP-${user.id}`}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <Mail className="h-3 w-3 text-indigo-400" /> Work Email
                      </span>
                      <p className="text-sm font-semibold text-gray-100 mt-1 break-all">{user.email}</p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <Phone className="h-3 w-3 text-indigo-400" /> Phone Number
                      </span>
                      <p className="text-sm font-semibold text-gray-100 mt-1">{user.phone || 'Not recorded'}</p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <Calendar className="h-3 w-3 text-indigo-400" /> Onboarding Date
                      </span>
                      <p className="text-sm font-semibold text-gray-100 mt-1">{formatDate(user.created_at)}</p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <Clock className="h-3 w-3 text-indigo-400" /> Last Active
                      </span>
                      <p className="text-sm font-semibold text-gray-100 mt-1">
                        {user.last_activity ? formatDate(user.last_activity) : 'Never recorded'}
                      </p>
                    </div>
                  </div>

                  {/* Biometric Status Summary Box */}
                  <div className="p-4 rounded-xl border border-gray-800 bg-gray-950/40 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-gray-200 flex items-center gap-2">
                        <Fingerprint className="h-4 w-4 text-cyan-400" />
                        Biometric Identity Protection
                      </span>
                      {user.has_face_enrolled ? (
                        <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
                          <CheckCircle2 className="h-3.5 w-3.5" /> Enrolled & Verified
                        </span>
                      ) : (
                        <span className="text-xs font-semibold text-amber-400 flex items-center gap-1">
                          <AlertCircle className="h-3.5 w-3.5" /> Template Missing
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400">
                      {user.has_face_enrolled
                        ? 'Encrypted neural face embedding is securely registered and active for biometric attendance and kiosk authentication.'
                        : 'No active face embedding on record. The user cannot use camera kiosks until face enrollment is completed.'}
                    </p>
                    {canEnroll && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onEnroll(user)}
                        className="text-xs border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 mt-1"
                      >
                        <Fingerprint className="h-3.5 w-3.5 mr-1" />
                        {user.has_face_enrolled ? 'Update Facial Template' : 'Enroll Biometrics Now'}
                      </Button>
                    )}
                  </div>
                </TabsContent>

                {/* Tab 2: Organization & Employment Details */}
                <TabsContent value="org" className="space-y-4 pt-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <Building2 className="h-3 w-3 text-indigo-400" /> Department
                      </span>
                      <p className="text-sm font-semibold text-gray-100 mt-1">
                        {user.department?.name || 'Unassigned'}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <Briefcase className="h-3 w-3 text-indigo-400" /> Designation / Job Title
                      </span>
                      <p className="text-sm font-semibold text-gray-100 mt-1">
                        {user.designation || 'Staff / Standard Member'}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <User className="h-3 w-3 text-indigo-400" /> Reporting Manager
                      </span>
                      <p className="text-sm font-semibold text-gray-100 mt-1">
                        {user.manager_name || 'None Assigned'}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <MapPin className="h-3 w-3 text-indigo-400" /> Branch / Location
                      </span>
                      <p className="text-sm font-semibold text-gray-100 mt-1">
                        {user.location || 'Headquarters'}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <Clock className="h-3 w-3 text-indigo-400" /> Assigned Shift
                      </span>
                      <p className="text-sm font-semibold text-gray-100 mt-1">
                        {user.shift?.shift_name || 'Standard 9-to-5'}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-gray-950/50 border border-gray-800/80">
                      <span className="text-[10px] uppercase font-bold text-gray-400 flex items-center gap-1.5">
                        <Briefcase className="h-3 w-3 text-indigo-400" /> Employment Classification
                      </span>
                      <div className="mt-1">
                        <EmploymentTypeBadge type={user.employment_type} />
                      </div>
                    </div>
                  </div>

                  {/* Connected Workforce & HCM Operations Quick Links */}
                  <div className="p-4 rounded-xl border border-gray-800 bg-gray-950/40 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-gray-200 flex items-center gap-2">
                        <Activity className="h-4 w-4 text-indigo-400" />
                        Connected Workforce & HCM Operations
                      </span>
                      <span className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">
                        Cross-Module Links
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => { onClose(); navigate('/dashboard/workforce/attendance'); }}
                        className="p-2.5 rounded-lg bg-gray-900/60 border border-gray-800 hover:border-indigo-500/50 hover:bg-gray-800/60 text-left transition-all group"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-gray-200 group-hover:text-indigo-300">Attendance</span>
                          <ArrowUpRight className="h-3.5 w-3.5 text-gray-500 group-hover:text-indigo-400" />
                        </div>
                        <p className="text-[10px] text-gray-400 mt-0.5">Logs & shift check-ins</p>
                      </button>

                      <button
                        type="button"
                        onClick={() => { onClose(); navigate('/dashboard/leave'); }}
                        className="p-2.5 rounded-lg bg-gray-900/60 border border-gray-800 hover:border-indigo-500/50 hover:bg-gray-800/60 text-left transition-all group"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-gray-200 group-hover:text-indigo-300">Leave Portal</span>
                          <ArrowUpRight className="h-3.5 w-3.5 text-gray-500 group-hover:text-indigo-400" />
                        </div>
                        <p className="text-[10px] text-gray-400 mt-0.5">Balances & requests</p>
                      </button>

                      <button
                        type="button"
                        onClick={() => { onClose(); navigate('/dashboard/performance'); }}
                        className="p-2.5 rounded-lg bg-gray-900/60 border border-gray-800 hover:border-indigo-500/50 hover:bg-gray-800/60 text-left transition-all group"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-gray-200 group-hover:text-indigo-300">Performance</span>
                          <ArrowUpRight className="h-3.5 w-3.5 text-gray-500 group-hover:text-indigo-400" />
                        </div>
                        <p className="text-[10px] text-gray-400 mt-0.5">Goals & review cycles</p>
                      </button>

                      <button
                        type="button"
                        onClick={() => { onClose(); navigate('/dashboard/payroll'); }}
                        className="p-2.5 rounded-lg bg-gray-900/60 border border-gray-800 hover:border-indigo-500/50 hover:bg-gray-800/60 text-left transition-all group"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-gray-200 group-hover:text-indigo-300">Payroll</span>
                          <ArrowUpRight className="h-3.5 w-3.5 text-gray-500 group-hover:text-indigo-400" />
                        </div>
                        <p className="text-[10px] text-gray-400 mt-0.5">Disbursements & slips</p>
                      </button>
                    </div>
                  </div>
                </TabsContent>

                {/* Tab 3: Access, Roles & Permissions */}
                <TabsContent value="access" className="space-y-4 pt-4">
                  <div className="p-4 rounded-xl bg-gray-950/50 border border-gray-800/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-gray-200 flex items-center gap-2">
                        <Shield className="h-4 w-4 text-purple-400" /> Assigned Role
                      </span>
                      <RoleBadge role={user.role} />
                    </div>
                    <p className="text-xs text-gray-400">
                      The role controls baseline module permissions, authorization boundaries, and policy evaluation.
                    </p>
                  </div>

                  {/* Effective Permissions Matrix */}
                  <div className="space-y-2">
                    <span className="text-xs font-bold text-gray-300 flex items-center justify-between">
                      <span>Effective Granted Permissions ({permissions.length})</span>
                      {loadingDetails && <Spinner size="sm" />}
                    </span>

                    <div className="max-h-48 overflow-y-auto p-3 bg-gray-950/80 border border-gray-800 rounded-xl space-y-1.5 hide-scrollbar">
                      {permissions.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {permissions.map((p) => (
                            <span
                              key={typeof p === 'string' ? p : p.name}
                              className="px-2 py-0.5 rounded-md text-[10px] font-mono font-medium bg-gray-900 border border-gray-800 text-indigo-300"
                            >
                              {typeof p === 'string' ? p : p.name}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-gray-500 text-center py-3">
                          {loadingDetails ? 'Resolving RBAC permissions...' : 'No explicit permissions assigned.'}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Trusted Devices & Sessions */}
                  <div className="space-y-2 pt-2">
                    <span className="text-xs font-bold text-gray-300 flex items-center gap-2">
                      <Laptop className="h-3.5 w-3.5 text-sky-400" /> Active Sessions & Devices ({trustedDevices.length})
                    </span>

                    <div className="space-y-2 max-h-44 overflow-y-auto hide-scrollbar">
                      {trustedDevices.length > 0 ? (
                        trustedDevices.map((d) => (
                          <div key={d.id} className="p-2.5 rounded-lg bg-gray-950/60 border border-gray-800 text-xs flex items-center justify-between">
                            <div>
                              <p className="font-semibold text-gray-200">{d.browser || 'Web Browser'} • {d.operating_system || 'Desktop'}</p>
                              <p className="text-[10px] text-gray-400 mt-0.5">IP: {d.ip_address || '127.0.0.1'}</p>
                            </div>
                            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                              Active
                            </span>
                          </div>
                        ))
                      ) : (
                        <p className="text-xs text-gray-500 text-center py-2">No active browser sessions.</p>
                      )}
                    </div>
                  </div>
                </TabsContent>

                {/* Tab 4: Audit & Lifecycle Timeline */}
                <TabsContent value="timeline" className="space-y-3 pt-4">
                  <span className="text-xs font-bold text-gray-300 flex items-center justify-between">
                    <span>Identity Lifecycle Audit Trail ({timelineEvents.length})</span>
                    {loadingDetails && <Spinner size="sm" />}
                  </span>

                  <div className="space-y-2.5 max-h-[360px] overflow-y-auto hide-scrollbar">
                    {timelineEvents.length > 0 ? (
                      timelineEvents.map((evt) => (
                        <div
                          key={evt.id}
                          className="p-3 rounded-xl bg-gray-950/60 border border-gray-800 text-xs space-y-1"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-indigo-400 uppercase tracking-wide">
                              {evt.event_type}
                            </span>
                            <span className="text-[10px] text-gray-500">
                              {evt.created_at ? new Date(evt.created_at).toLocaleString() : '—'}
                            </span>
                          </div>
                          {evt.reason && (
                            <p className="text-gray-300 text-xs">
                              <span className="text-gray-500">Reason:</span> {evt.reason}
                            </p>
                          )}
                          {evt.performed_by && (
                            <p className="text-[10px] text-gray-400">
                              Executed by: {evt.performed_by.full_name || evt.performed_by.email}
                            </p>
                          )}
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-gray-500 text-center py-6">
                        {loadingDetails ? 'Retrieving audit events...' : 'No identity state changes recorded yet.'}
                      </p>
                    )}
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          </motion.div>
        </div>
      </div>
    </AnimatePresence>
  );
}

export default UserDetailDrawer;
