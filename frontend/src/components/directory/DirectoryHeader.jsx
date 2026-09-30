/**
 * DirectoryHeader.jsx
 * Header component for the Enterprise Identity Directory & User Management page.
 * Strictly adheres to Phase 2 theme engine (Dark, Light, Midnight, Nordic).
 */
import React from 'react';
import { Users, UserPlus, RefreshCw } from 'lucide-react';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';

export function DirectoryHeader({
  totalCount = 0,
  canCreate = false,
  onCreate,
  onRefresh,
  refreshing = false,
  orgName = ''
}) {
  return (
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 glass bg-gray-900/60 border border-gray-800/80 rounded-2xl p-6 shadow-xl backdrop-blur-xl transition-colors">
      <div className="space-y-1.5">
        <div className="flex items-center flex-wrap gap-2.5">
          <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Users className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-100 tracking-tight">
                Identity Directory & Workforce
              </h1>
              <Badge variant="primary" className="text-xs font-semibold uppercase px-2.5 py-0.5">
                Tenant Scoped
              </Badge>
              {totalCount > 0 && (
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 border border-gray-700">
                  {totalCount} {totalCount === 1 ? 'identity' : 'identities'}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-400 mt-1 flex items-center flex-wrap gap-2">
              <span>Canonical lifecycle management for employees, contractors, managers, and system identities</span>
              {orgName && (
                <>
                  <span className="inline-block h-1 w-1 rounded-full bg-gray-600" />
                  <span className="text-indigo-400 font-semibold">{orgName}</span>
                </>
              )}
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2.5 shrink-0 self-start sm:self-auto">
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          disabled={refreshing}
          className="border-gray-800 bg-gray-900/80 text-gray-300 hover:bg-gray-800 hover:text-gray-100"
          aria-label="Refresh Directory"
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? 'animate-spin text-indigo-400' : ''}`} />
          Refresh
        </Button>

        {canCreate && (
          <Button
            onClick={onCreate}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-4 py-2 rounded-xl shadow-lg shadow-indigo-500/20"
            aria-label="Provision New Identity"
          >
            <UserPlus className="h-4 w-4 mr-1.5" />
            Provision Identity
          </Button>
        )}
      </div>
    </div>
  );
}

export default DirectoryHeader;
