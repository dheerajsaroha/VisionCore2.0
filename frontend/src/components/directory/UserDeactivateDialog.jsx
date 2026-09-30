/**
 * UserDeactivateDialog.jsx
 * Enterprise account suspension & deactivation dialog with consequence warnings
 * and mandatory reason collection for audit history compliance.
 */
import React, { useState } from 'react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { UserX, AlertTriangle, ShieldAlert } from 'lucide-react';

export function UserDeactivateDialog({
  isOpen,
  onClose,
  user,
  onConfirm,
  loading = false,
}) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');

  if (!isOpen || !user) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!reason.trim()) {
      setError('A suspension reason is strictly required for compliance logging.');
      return;
    }
    setError('');
    try {
      await onConfirm(user.id, reason.trim());
      setReason('');
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to suspend account.');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Suspend Identity: ${user.full_name}`}
      description="Temporarily revoke system access and biometric check-in authorization."
      size="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 pt-2 text-xs">
        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Security Consequence Warning Box */}
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-200 space-y-2">
          <div className="flex items-center gap-2 font-bold text-amber-400">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span>Immediate Security Consequences:</span>
          </div>
          <ul className="list-disc pl-5 space-y-1 text-[11px] text-amber-300/90 leading-relaxed">
            <li>All active browser sessions and mobile tokens will be revoked immediately.</li>
            <li>Biometric facial check-ins at attendance kiosks will be denied.</li>
            <li>The user will remain listed in the directory with status <span className="font-semibold text-rose-300">Suspended</span>.</li>
            <li>This action is reversible by an authorized administrator at any time.</li>
          </ul>
        </div>

        {/* Mandatory Reason Field */}
        <div className="space-y-1.5">
          <label className="font-semibold text-gray-200 block">
            Compliance Suspension Reason *
          </label>
          <textarea
            required
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Leave of absence, security investigation, contract expiration pending renewal..."
            className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 text-xs p-3 rounded-xl focus:border-amber-500 outline-none transition-colors resize-none"
          />
          <p className="text-[10px] text-gray-500">
            Recorded immutably in the tenant's security audit trail and identity timeline.
          </p>
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
            type="submit"
            disabled={loading || !reason.trim()}
            className="bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-amber-500/20"
          >
            <UserX className="h-3.5 w-3.5 mr-1.5" />
            {loading ? 'Suspending...' : 'Confirm Suspension'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default UserDeactivateDialog;
