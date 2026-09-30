/**
 * UserActions.jsx
 * Row actions dropdown and quick action triggers with RBAC permission enforcement.
 * Adheres to Phase 2 theme styling.
 */
import React, { useState, useRef, useEffect } from 'react';
import {
  MoreVertical,
  Eye,
  Edit3,
  Shield,
  Fingerprint,
  History,
  UserX,
  UserCheck,
  Trash2
} from 'lucide-react';
import { Button } from '../ui/Button';

export function UserActions({
  user,
  currentUserId,
  canEdit = false,
  canDelete = false,
  canAssignRole = false,
  canViewTimeline = true,
  onView,
  onEdit,
  onAssignRole,
  onActivate,
  onSuspend,
  onEnroll,
  onTimeline,
  onDelete,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);

  const isSelf = currentUserId === user.id;
  const canModifyStatus = canEdit && !isSelf;
  const canDeleteUser = canDelete && !isSelf;
  // POST /users/{id}/enroll[-face] permits self-enrollment or users.update.
  const canEnroll = Boolean(onEnroll) && (isSelf || canEdit);

  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  return (
    <div className="relative inline-flex items-center gap-1" ref={menuRef} onClick={(e) => e.stopPropagation()}>
      {/* Primary quick action: View Profile */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onView(user)}
        className="h-8 w-8 p-0 text-gray-400 hover:text-indigo-400 hover:bg-indigo-500/10 rounded-lg"
        title="View Identity Profile"
        aria-label={`View profile of ${user.full_name}`}
      >
        <Eye className="h-4 w-4" />
      </Button>

      {/* Overflow Menu Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="p-1.5 rounded-lg text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition-colors focus:outline-none focus:ring-1 focus:ring-indigo-500"
        aria-expanded={isOpen}
        aria-label={`More actions for ${user.full_name}`}
      >
        <MoreVertical className="h-4 w-4" />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          className="absolute right-0 top-9 z-50 w-52 glass bg-gray-900/95 border border-gray-800 rounded-xl shadow-2xl py-1.5 backdrop-blur-xl animate-fade-in text-xs font-medium divide-y divide-gray-800/80"
          role="menu"
        >
          {/* View & Details Section */}
          <div className="py-1">
            <button
              onClick={() => { onView(user); setIsOpen(false); }}
              className="w-full text-left px-3.5 py-2 text-gray-300 hover:text-indigo-300 hover:bg-gray-800/60 flex items-center gap-2.5 transition-colors"
              role="menuitem"
            >
              <Eye className="h-3.5 w-3.5 text-gray-400" />
              <span>View Full Dossier</span>
            </button>

            {canViewTimeline && onTimeline && (
              <button
                onClick={() => { onTimeline(user); setIsOpen(false); }}
                className="w-full text-left px-3.5 py-2 text-gray-300 hover:text-indigo-300 hover:bg-gray-800/60 flex items-center gap-2.5 transition-colors"
                role="menuitem"
              >
                <History className="h-3.5 w-3.5 text-indigo-400" />
                <span>Lifecycle Timeline</span>
              </button>
            )}
          </div>

          {/* Modification Section */}
          {(canEdit || canAssignRole) && (
            <div className="py-1">
              {canEdit && onEdit && (
                <button
                  onClick={() => { onEdit(user); setIsOpen(false); }}
                  className="w-full text-left px-3.5 py-2 text-gray-300 hover:text-indigo-300 hover:bg-gray-800/60 flex items-center gap-2.5 transition-colors"
                  role="menuitem"
                >
                  <Edit3 className="h-3.5 w-3.5 text-sky-400" />
                  <span>Edit Profile</span>
                </button>
              )}

              {canAssignRole && onAssignRole && (
                <button
                  onClick={() => { onAssignRole(user); setIsOpen(false); }}
                  className="w-full text-left px-3.5 py-2 text-gray-300 hover:text-purple-300 hover:bg-gray-800/60 flex items-center gap-2.5 transition-colors"
                  role="menuitem"
                >
                  <Shield className="h-3.5 w-3.5 text-purple-400" />
                  <span>Assign Role</span>
                </button>
              )}

              {canEnroll && (
                <button
                  onClick={() => { onEnroll(user); setIsOpen(false); }}
                  className="w-full text-left px-3.5 py-2 text-gray-300 hover:text-cyan-300 hover:bg-gray-800/60 flex items-center gap-2.5 transition-colors"
                  role="menuitem"
                >
                  <Fingerprint className="h-3.5 w-3.5 text-cyan-400" />
                  <span>{user.has_face_enrolled ? 'Re-enroll Biometric' : 'Enroll Biometric'}</span>
                </button>
              )}
            </div>
          )}

          {/* Lifecycle State Mutations */}
          {canModifyStatus && (
            <div className="py-1">
              {user.is_active ? (
                <button
                  onClick={() => { onSuspend(user); setIsOpen(false); }}
                  className="w-full text-left px-3.5 py-2 text-amber-400 hover:text-amber-300 hover:bg-amber-500/10 flex items-center gap-2.5 transition-colors"
                  role="menuitem"
                >
                  <UserX className="h-3.5 w-3.5" />
                  <span>Suspend Account</span>
                </button>
              ) : (
                <button
                  onClick={() => { onActivate(user); setIsOpen(false); }}
                  className="w-full text-left px-3.5 py-2 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10 flex items-center gap-2.5 transition-colors"
                  role="menuitem"
                >
                  <UserCheck className="h-3.5 w-3.5" />
                  <span>Activate Account</span>
                </button>
              )}
            </div>
          )}

          {/* Destructive Section */}
          {canDeleteUser && onDelete && (
            <div className="py-1">
              <button
                onClick={() => { onDelete(user); setIsOpen(false); }}
                className="w-full text-left px-3.5 py-2 text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 flex items-center gap-2.5 transition-colors"
                role="menuitem"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Archive / Remove</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default UserActions;
