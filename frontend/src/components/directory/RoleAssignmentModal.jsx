/**
 * RoleAssignmentModal.jsx
 * Enterprise RBAC Role Assignment dialog.
 * Requires roles.assign permission; displays role capability summaries and confirmation safeguards.
 */
import React, { useState } from 'react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';

const ROLE_DESCRIPTIONS = {
  SuperAdmin: 'Platform-level administrator with unrestricted global access across all tenants.',
  OrgAdmin: 'Organization administrator with complete control over tenant users, roles, and settings.',
  HR: 'Human Resources operator with workforce lifecycle, recruitment, policy, and attendance authority.',
  Finance: 'Financial operator with access to payroll generation, disbursements, and billing reports.',
  Manager: 'Team and department supervisor with leave approval and team roster authority.',
  Employee: 'Standard workforce self-service member with attendance check-in and request capabilities.',
};

export function RoleAssignmentModal({
  isOpen,
  onClose,
  user,
  roles = [],
  onAssign,
  loading = false,
}) {
  const currentRoleName = user?.role?.name || user?.role || 'Employee';
  const [selectedRole, setSelectedRole] = useState(currentRoleName);
  const [error, setError] = useState('');

  if (!isOpen || !user) return null;

  const handleConfirm = async () => {
    if (selectedRole === currentRoleName) {
      onClose();
      return;
    }
    setError('');
    try {
      await onAssign(user.id, selectedRole);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update user role.');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Assign Role: ${user.full_name}`}
      description="Modify access tier and baseline permission taxonomy for this identity."
      size="md"
    >
      <div className="space-y-4 pt-2 text-xs">
        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Current Role Banner */}
        <div className="p-3 rounded-xl bg-gray-950/60 border border-gray-800 flex items-center justify-between">
          <span className="text-gray-400">Current Assigned Role:</span>
          <span className="font-bold text-gray-100 px-2.5 py-0.5 rounded-full bg-gray-800 border border-gray-700">
            {currentRoleName}
          </span>
        </div>

        {/* Role Selector */}
        <div className="space-y-2">
          <label className="font-semibold text-gray-200 block">
            Target Role Assignment:
          </label>
          <div className="grid grid-cols-1 gap-2">
            {(roles.length > 0 ? roles.map((r) => r.name) : ['Employee', 'Manager', 'HR', 'Finance', 'OrgAdmin']).map((rName) => (
              <label
                key={rName}
                className={`p-3 rounded-xl border flex items-start gap-3 cursor-pointer transition-all ${
                  selectedRole === rName
                    ? 'border-indigo-500 bg-indigo-500/10 ring-1 ring-indigo-500/30'
                    : 'border-gray-800 bg-gray-950/40 hover:bg-gray-800/40'
                }`}
              >
                <input
                  type="radio"
                  name="roleAssignment"
                  value={rName}
                  checked={selectedRole === rName}
                  onChange={(e) => setSelectedRole(e.target.value)}
                  className="mt-0.5 text-indigo-600 focus:ring-indigo-500"
                />
                <div className="space-y-0.5">
                  <div className="font-bold text-gray-100 flex items-center gap-2">
                    <span>{rName}</span>
                    {selectedRole === rName && (
                      <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400" />
                    )}
                  </div>
                  <p className="text-[11px] text-gray-400 leading-normal">
                    {ROLE_DESCRIPTIONS[rName] || 'Standard organizational role binding.'}
                  </p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Audit Warning */}
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px] flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>
            Modifying role immediately recalculates effective permissions, revokes unauthorized cached scopes, and generates a tamper-evident audit log event.
          </span>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-800/80">
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
            type="button"
            onClick={handleConfirm}
            disabled={loading || selectedRole === currentRoleName}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-indigo-500/20"
          >
            {loading ? 'Reassigning...' : 'Confirm Role Change'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default RoleAssignmentModal;
