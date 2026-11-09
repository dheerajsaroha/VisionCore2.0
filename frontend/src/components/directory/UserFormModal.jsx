/**
 * UserFormModal.jsx
 * Unified form modal for provisioning new identities and updating existing profiles.
 * Backed by real validation, RBAC checks, and Phase 2 styling.
 */
import React, { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import '../ui/Input';
import '../ui/Select';
import { User, Mail, Lock, Phone, Hash, Building2, Clock, Briefcase, Shield, AlertCircle, MapPin } from 'lucide-react';

export function UserFormModal({
  isOpen,
  onClose,
  mode = 'create', // 'create' | 'edit'
  initialUser = null,
  departments = [],
  shifts = [],
  branches = [],
  managers = [],
  canAssignRole = false,
  onSubmit,
  loading = false,
}) {
  const isEdit = mode === 'edit';

  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    password: '',
    phone: '',
    employee_id: '',
    role: 'Employee',
    dept_id: '',
    shift_id: '',
    branch_id: '',
    designation: '',
    employment_type: 'EMPLOYEE',
    reporting_manager_id: '',
    is_active: 1,
  });

  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    if (isEdit && initialUser) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Synchronizes editable form state with the selected record.
      setFormData({
        full_name: initialUser.full_name || '',
        email: initialUser.email || '',
        password: '',
        phone: initialUser.phone || '',
        employee_id: initialUser.employee_id || '',
        role: initialUser.role?.name || initialUser.role || 'Employee',
        dept_id: initialUser.dept_id ? String(initialUser.dept_id) : '',
        shift_id: initialUser.shift_id ? String(initialUser.shift_id) : '',
        branch_id: initialUser.branch_id ? String(initialUser.branch_id) : '',
        designation: initialUser.designation || '',
        employment_type: initialUser.employment_type || 'EMPLOYEE',
        reporting_manager_id: initialUser.manager_id ? String(initialUser.manager_id) : '',
        is_active: initialUser.is_active !== undefined ? initialUser.is_active : 1,
      });
    } else {
      setFormData({
        full_name: '',
        email: '',
        password: '',
        phone: '',
        employee_id: '',
        role: 'Employee',
        dept_id: '',
        shift_id: '',
        branch_id: '',
        designation: '',
        employment_type: 'EMPLOYEE',
        reporting_manager_id: '',
        is_active: 1,
      });
    }
    setErrorMessage('');
  }, [isOpen, isEdit, initialUser]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');

    // Basic validation
    if (!formData.full_name.trim()) {
      setErrorMessage('Full name is required.');
      return;
    }
    if (!isEdit) {
      if (!formData.email.trim()) {
        setErrorMessage('Email address is required.');
        return;
      }
      if (!formData.password || formData.password.length < 6) {
        setErrorMessage('Password must be at least 6 characters long.');
        return;
      }
    }

    try {
      const payload = {
        full_name: formData.full_name.trim(),
        phone: formData.phone.trim() || null,
        dept_id: formData.dept_id ? Number(formData.dept_id) : null,
        shift_id: formData.shift_id ? Number(formData.shift_id) : null,
        branch_id: formData.branch_id ? Number(formData.branch_id) : null,
        designation: formData.designation.trim() || null,
        employment_type: formData.employment_type || 'EMPLOYEE',
        reporting_manager_id: formData.reporting_manager_id ? Number(formData.reporting_manager_id) : null,
      };

      if (!isEdit) {
        payload.email = formData.email.trim().toLowerCase();
        payload.password = formData.password;
        payload.role = formData.role || 'Employee';
        if (formData.employee_id.trim()) {
          payload.employee_id = formData.employee_id.trim();
        }
      } else {
        if (canAssignRole && formData.role) {
          payload.role = formData.role;
        }
        payload.is_active = Number(formData.is_active);
      }

      await onSubmit(payload);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setErrorMessage(typeof detail === 'string' ? detail : 'An unexpected error occurred.');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? `Edit Profile: ${initialUser?.full_name}` : 'Provision New Identity'}
      description={
        isEdit
          ? 'Update organizational assignments, contact information, and role bindings.'
          : 'Create a new workforce identity scoped to your organization.'
      }
      size="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4 pt-2">
        {errorMessage && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Full Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <User className="h-3.5 w-3.5 text-indigo-400" />
              Full Name *
            </label>
            <input
              type="text"
              required
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              placeholder="e.g. Sarah Jenkins"
              className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            />
          </div>

          {/* Email Address */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <Mail className="h-3.5 w-3.5 text-indigo-400" />
              Work Email {isEdit ? '(Immutable)' : '*'}
            </label>
            <input
              type="email"
              required={!isEdit}
              disabled={isEdit}
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="s.jenkins@company.com"
              className={`w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors ${
                isEdit ? 'opacity-60 cursor-not-allowed' : ''
              }`}
            />
          </div>

          {/* Password (Only in create mode) */}
          {!isEdit && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
                <Lock className="h-3.5 w-3.5 text-indigo-400" />
                Temporary Password *
              </label>
              <input
                type="password"
                required
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder="Min. 6 characters"
                className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
              />
            </div>
          )}

          {/* Employee ID */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <Hash className="h-3.5 w-3.5 text-indigo-400" />
              Employee ID {isEdit ? '(Immutable)' : '(Auto-generated if empty)'}
            </label>
            <input
              type="text"
              disabled={isEdit}
              value={formData.employee_id}
              onChange={(e) => setFormData({ ...formData, employee_id: e.target.value })}
              placeholder="e.g. EMP-10492"
              className={`w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors font-mono ${
                isEdit ? 'opacity-60 cursor-not-allowed' : ''
              }`}
            />
          </div>

          {/* Phone */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <Phone className="h-3.5 w-3.5 text-indigo-400" />
              Phone Number
            </label>
            <input
              type="tel"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              placeholder="+1 555-0199"
              className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            />
          </div>

          {/* Role */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <Shield className="h-3.5 w-3.5 text-indigo-400" />
              Role Assignment {!canAssignRole && isEdit ? '(Protected)' : ''}
            </label>
            <select
              disabled={isEdit && !canAssignRole}
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              className={`w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors ${
                isEdit && !canAssignRole ? 'opacity-60 cursor-not-allowed' : ''
              }`}
            >
              <option value="Employee">Employee</option>
              <option value="Manager">Manager</option>
              {canAssignRole && (
                <>
                  <option value="HR">HR</option>
                  <option value="Finance">Finance</option>
                  <option value="OrgAdmin">OrgAdmin</option>
                </>
              )}
            </select>
          </div>

          {/* Department */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <Building2 className="h-3.5 w-3.5 text-indigo-400" />
              Department
            </label>
            <select
              value={formData.dept_id}
              onChange={(e) => setFormData({ ...formData, dept_id: e.target.value })}
              className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            >
              <option value="">Unassigned</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>

          {/* Shift */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-indigo-400" />
              Shift Assignment
            </label>
            <select
              value={formData.shift_id}
              onChange={(e) => setFormData({ ...formData, shift_id: e.target.value })}
              className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            >
              <option value="">Standard Shift</option>
              {shifts.map((s) => (
                <option key={s.id} value={s.id}>{s.shift_name}</option>
              ))}
            </select>
          </div>

          {/* Branch / Location */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <MapPin className="h-3.5 w-3.5 text-indigo-400" />
              Branch / Location
            </label>
            <select
              value={formData.branch_id}
              onChange={(e) => setFormData({ ...formData, branch_id: e.target.value })}
              className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            >
              <option value="">Headquarters / Primary</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>{b.name}{b.city ? ` (${b.city})` : ''}</option>
              ))}
            </select>
          </div>

          {/* Designation */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <Briefcase className="h-3.5 w-3.5 text-indigo-400" />
              Designation / Job Title
            </label>
            <input
              type="text"
              value={formData.designation}
              onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
              placeholder="e.g. Lead Engineer"
              className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            />
          </div>

          {/* Employment Type */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <Briefcase className="h-3.5 w-3.5 text-indigo-400" />
              Employment Classification
            </label>
            <select
              value={formData.employment_type}
              onChange={(e) => setFormData({ ...formData, employment_type: e.target.value })}
              className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            >
              <option value="EMPLOYEE">Regular Employee</option>
              <option value="CONTRACTOR">Contractor</option>
              <option value="CONSULTANT">Consultant</option>
              <option value="VENDOR">Vendor</option>
              <option value="INTERN">Intern</option>
            </select>
          </div>

          {/* Reporting Manager */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <User className="h-3.5 w-3.5 text-indigo-400" />
              Reporting Manager
            </label>
            <select
              value={formData.reporting_manager_id}
              onChange={(e) => setFormData({ ...formData, reporting_manager_id: e.target.value })}
              className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            >
              <option value="">None (Top Level / Direct)</option>
              {managers
                .filter((m) => !isEdit || m.id !== initialUser?.id)
                .map((m) => (
                  <option key={m.id} value={m.id}>{m.full_name} ({m.role?.name || 'User'})</option>
                ))}
            </select>
          </div>

          {/* Status (Edit mode only) */}
          {isEdit && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
                <Shield className="h-3.5 w-3.5 text-indigo-400" />
                Account Status
              </label>
              <select
                value={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: Number(e.target.value) })}
                className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
              >
                <option value={1}>Active</option>
                <option value={0}>Suspended / Inactive</option>
              </select>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800/80">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={loading}
            className="text-xs text-gray-400 hover:text-gray-100"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={loading}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-indigo-500/20"
          >
            {loading ? 'Saving...' : isEdit ? 'Update Identity' : 'Provision Identity'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default UserFormModal;
