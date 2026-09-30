/**
 * IdentityTimelineModal.jsx
 * Audit trail modal displaying chronological lifecycle mutations and security events.
 * Fetches real event history from GET /identity/{id}/timeline.
 */
import React, { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import { History, Calendar, User, Shield, ArrowRight } from 'lucide-react';
import userService from '../../services/userService';

export function IdentityTimelineModal({
  isOpen,
  onClose,
  user,
}) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isOpen || !user?.id) return;
    let isMounted = true;

    const fetchTimeline = async () => {
      setLoading(true);
      try {
        const res = await userService.getIdentityTimeline(user.id);
        if (isMounted) {
          setEvents(res.data || []);
        }
      } catch (err) {
        if (isMounted) setEvents([]);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchTimeline();
    return () => { isMounted = false; };
  }, [isOpen, user?.id]);

  if (!isOpen || !user) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Identity Lifecycle Timeline: ${user.full_name}`}
      description="Cryptographically logged audit history of state transitions and status alterations."
      size="md"
    >
      <div className="space-y-4 pt-2 text-xs">
        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center gap-3">
            <Spinner size="lg" className="text-indigo-500" />
            <span className="text-gray-400">Loading audit log events...</span>
          </div>
        ) : events.length === 0 ? (
          <div className="py-10 text-center space-y-2">
            <History className="h-8 w-8 text-gray-600 mx-auto" />
            <p className="font-semibold text-gray-300">No Lifecycle Events Found</p>
            <p className="text-gray-500 text-[11px]">
              This account has not had any administrative state transitions or status alterations recorded yet.
            </p>
          </div>
        ) : (
          <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-800">
            {events.map((evt, idx) => (
              <div key={evt.id || idx} className="relative space-y-1">
                {/* Timeline Node Dot */}
                <div className="absolute -left-6 top-1.5 h-3 w-3 rounded-full border-2 border-gray-900 bg-indigo-500 ring-2 ring-indigo-500/20" />

                <div className="p-3 rounded-xl bg-gray-950/60 border border-gray-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-indigo-400 uppercase tracking-wide">
                      {evt.event_type}
                    </span>
                    <span className="text-[10px] text-gray-500 font-mono">
                      {evt.created_at ? new Date(evt.created_at).toLocaleString() : '—'}
                    </span>
                  </div>

                  {evt.reason && (
                    <p className="text-gray-300 text-[11px]">
                      <span className="text-gray-500 font-semibold">Reason:</span> {evt.reason}
                    </p>
                  )}

                  {evt.performed_by && (
                    <p className="text-[10px] text-gray-400 flex items-center gap-1 pt-1 border-t border-gray-900">
                      <User className="h-3 w-3 text-gray-500" />
                      <span>Executed by: {evt.performed_by.full_name || evt.performed_by.email}</span>
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-end pt-3 border-t border-gray-800/80">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            className="text-xs text-gray-400 hover:text-gray-100"
          >
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default IdentityTimelineModal;
