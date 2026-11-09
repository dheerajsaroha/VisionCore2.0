import React, { useState, useEffect } from 'react';
import { X, Mail, User, Clock, AlertCircle } from 'lucide-react';
import { userService } from '../services/userService';
import { attendanceService } from '../services/attendanceService';
import { Avatar } from './ui/Avatar';
import { Badge } from './ui/Badge';

export function EmployeeDetailModal({ userId, isOpen, onClose }) {
  const [employee, setEmployee] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen || !userId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Clear stale detail data when the modal closes or target is missing.
      setEmployee(null);
      setSummary(null);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError('');

    Promise.all([
      userService.getUserById(userId),
      attendanceService.getAttendanceSummary({ user_id: userId }),
    ])
      .then(([userRes, summaryRes]) => {
        if (!isMounted) return;
        setEmployee(userRes.data || userRes);
        setSummary(summaryRes.data || summaryRes);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err.response?.data?.detail || 'Failed to load employee details.');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, userId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gray-950/50">
          <div className="flex items-center gap-2">
            <User className="h-5 w-5 text-indigo-400" />
            <h3 className="text-lg font-semibold text-white">Employee Profile Details</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 max-h-[80vh] overflow-y-auto hide-scrollbar">
          {loading && (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!loading && employee && (
            <>
              {/* Profile Card Header */}
              <div className="flex items-start gap-4 p-4 rounded-xl bg-gray-800/40 border border-gray-800">
                <Avatar name={employee.full_name} size="xl" />
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 className="text-lg font-bold text-white truncate">{employee.full_name}</h4>
                    <Badge variant={employee.is_active ? 'success' : 'secondary'}>
                      {employee.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                  <p className="text-sm text-gray-400 font-mono">@{employee.username}</p>
                  <div className="flex items-center gap-1.5 text-sm text-gray-300">
                    <Mail className="h-3.5 w-3.5 text-gray-500" />
                    <span className="truncate">{employee.email}</span>
                  </div>
                </div>
              </div>

              {/* Identity & Employment Details */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-3 rounded-xl bg-gray-800/20 border border-gray-800">
                  <span className="text-xs text-gray-500 block uppercase font-medium">Employee ID</span>
                  <span className="font-semibold text-gray-200 font-mono">{employee.employee_id || 'N/A'}</span>
                </div>
                <div className="p-3 rounded-xl bg-gray-800/20 border border-gray-800">
                  <span className="text-xs text-gray-500 block uppercase font-medium">Role</span>
                  <span className="font-semibold text-indigo-400">{employee.role?.name || employee.role || 'Employee'}</span>
                </div>
                <div className="p-3 rounded-xl bg-gray-800/20 border border-gray-800">
                  <span className="text-xs text-gray-500 block uppercase font-medium">Organization</span>
                  <span className="font-semibold text-gray-200">{employee.organization?.name || employee.organization || 'VisionCore'}</span>
                </div>
                <div className="p-3 rounded-xl bg-gray-800/20 border border-gray-800">
                  <span className="text-xs text-gray-500 block uppercase font-medium">Member Since</span>
                  <span className="font-semibold text-gray-200">
                    {employee.created_at ? new Date(employee.created_at).toLocaleDateString() : 'N/A'}
                  </span>
                </div>
              </div>

              {/* Monthly Attendance Summary */}
              {summary && (
                <div className="space-y-3 pt-2">
                  <h5 className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
                    <Clock className="h-4 w-4 text-indigo-400" />
                    Monthly Attendance Metrics
                  </h5>
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20">
                      <p className="text-2xl font-extrabold text-indigo-400">{summary.present_count ?? 0}</p>
                      <p className="text-xs text-gray-400 mt-0.5">Days Present</p>
                    </div>
                    <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
                      <p className="text-2xl font-extrabold text-amber-400">{summary.late_count ?? 0}</p>
                      <p className="text-xs text-gray-400 mt-0.5">Late Arrivals</p>
                    </div>
                    <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                      <p className="text-2xl font-extrabold text-emerald-400">{summary.attendance_rate_pct ?? 0}%</p>
                      <p className="text-xs text-gray-400 mt-0.5">Rate</p>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-800 bg-gray-950/50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-xl bg-gray-800 text-gray-200 hover:bg-gray-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
