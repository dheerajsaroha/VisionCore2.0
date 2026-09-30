/**
 * BiometricAvatar.jsx
 * Renders the capture registered with an employee's biometric template, falling
 * back to the employee's initials. The capture is served from an authenticated,
 * tenant-scoped endpoint, so it is loaded as a blob and cached per user.
 *
 * That endpoint refuses anyone but the subject and holders of `users.update`.
 * The attendance feed renders this component for *other* employees, so without
 * a check here every viewer without that permission fired one 403 per avatar on
 * every dashboard load. The component now declines to ask, rather than asking
 * and swallowing the error.
 */
import React, { useEffect, useState } from 'react';
import userService from '../../services/userService';
import { useAuthStore } from '../../store/authStore';
import { usePermission } from '../../hooks/usePermission';

export function BiometricAvatar({ userId, name, size = 'h-9 w-9', textClass = 'text-sm', className = '' }) {
  const [photoUrl, setPhotoUrl] = useState(null);
  const user = useAuthStore((s) => s.user);
  const { hasPermission } = usePermission();

  // The photo is either the viewer's own, or one the viewer may read for
  // someone else. Anything else resolves to the initials fallback.
  //
  // Before permissions are hydrated this is false, so the request is deferred
  // rather than fired optimistically and then rejected.
  const canView = Boolean(userId) && (
    (user && Number(user.id) === Number(userId)) || hasPermission('users.update')
  );

  useEffect(() => {
    let active = true;
    setPhotoUrl(null);
    if (!userId || !canView) return undefined;

    userService.getFacePhotoUrl(userId).then((url) => {
      if (active) setPhotoUrl(url);
    });

    return () => {
      active = false;
    };
  }, [userId, canView]);

  const initial = (name || '?').trim().charAt(0).toUpperCase() || '?';

  if (photoUrl) {
    return (
      <img
        src={photoUrl}
        alt={name ? `${name} biometric template` : 'Biometric template'}
        title="Biometric enrollment capture"
        className={`${size} rounded-full object-cover shrink-0 border border-gray-700 ${className}`}
      />
    );
  }

  return (
    <div
      title={name ? `${name} — no enrollment photo` : 'No enrollment photo'}
      className={`${size} rounded-full bg-gray-800 text-gray-300 flex items-center justify-center ${textClass} font-bold shrink-0 ${className}`}
    >
      {initial}
    </div>
  );
}

export default BiometricAvatar;
