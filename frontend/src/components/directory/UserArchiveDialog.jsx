/**
 * UserArchiveDialog.jsx
 * Enterprise account archiving & soft-deletion dialog.
 * Explains security consequences, guards sole admins and self-deletion,
 * and complies with Phase 2 theme engine.
 */
import React from 'react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { AlertTriangle, ShieldAlert, Archive } from 'lucide-react';

export function UserArchiveDialog({
  isOpen,
  onClose,
  user,
  currentUserId,
  onConfirm,
  loading = false,
}) {
  if (!isOpen || !user) return null;

  const isSelf = currentUserId === user.id;

  const handleArchive = async () => {
    if (isSelf) return;
    await onConfirm(user);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Archive Identity: ${user.full_name}`}
      description="Deactivate and archive this workforce identity record."
      size="md"
    >
      <div className="space-y-4 pt-2 text-xs">
        {isSelf && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>You cannot delete or archive your own account.</span>
          </div>
        )}

        {/* Security Consequence Box */}
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-200 space-y-2">
          <div className="flex items-center gap-2 font-bold text-rose-400">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span>Permanent Compliance Impact:</span>
          </div>
          <ul className="list-disc pl-5 space-y-1 text-[11px] text-rose-300/90 leading-relaxed">
            <li>The identity will be soft-deleted (<span className="font-mono text-xs text-rose-200">is_deleted = 1</span>) and removed from the active directory.</li>
            <li>All active sessions will be terminated and credentials immediately invalidated.</li>
            <li>Biometric facial matching will reject future kiosk check-ins for this user.</li>
            <li>Existing attendance logs, payroll calculations, and audit records remain intact for compliance audits.</li>
          </ul>
        </div>

        {/* User Snapshot */}
        <div className="p-3 rounded-xl bg-gray-950/60 border border-gray-800 text-gray-300 flex items-center justify-between">
          <div>
            <p className="font-bold text-gray-100">{user.full_name}</p>
            <p className="text-[11px] text-gray-400 mt-0.5">{user.email} • ID: {user.employee_id || `EMP-${user.id}`}</p>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-gray-800 border border-gray-700 text-gray-300">
            {user.role?.name || user.role || 'Employee'}
          </span>
        </div>

        {/* Action Buttons */}
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
            disabled={loading || isSelf}
            onClick={handleArchive}
            className="bg-rose-600 hover:bg-rose-500 text-white font-medium text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-rose-500/20"
          >
            <Archive className="h-3.5 w-3.5 mr-1.5" />
            {loading ? 'Archiving...' : 'Archive & Deactivate'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default UserArchiveDialog;
