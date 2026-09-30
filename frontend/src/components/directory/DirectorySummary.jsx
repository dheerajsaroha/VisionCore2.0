/**
 * DirectorySummary.jsx
 * KPI summary metrics cards for the Identity Directory.
 * Strictly backed by real aggregations from GET /users/summary.
 */
import React from 'react';
import { Users, UserCheck, UserX, Shield, Fingerprint } from 'lucide-react';
import { Card, CardContent } from '../ui/Card';
import { Skeleton } from '../ui/Skeleton';

export function DirectorySummary({
  total = 0,
  activeCount = 0,
  inactiveCount = 0,
  adminCount = 0,
  enrolledCount = 0,
  loading = false
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-24 bg-gray-800/60 rounded-2xl" />
        ))}
      </div>
    );
  }

  const items = [
    {
      title: 'Total Managed',
      value: total,
      subtitle: 'Tenant identities',
      icon: Users,
      accent: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
      bar: 'bg-indigo-500',
    },
    {
      title: 'Active Accounts',
      value: activeCount,
      subtitle: `${total > 0 ? Math.round((activeCount / total) * 100) : 100}% operational`,
      icon: UserCheck,
      accent: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
      bar: 'bg-emerald-500',
    },
    {
      title: 'Suspended / Inactive',
      value: inactiveCount,
      subtitle: 'Restricted access',
      icon: UserX,
      accent: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
      bar: 'bg-rose-500',
    },
    {
      title: 'Privileged Roles',
      value: adminCount,
      subtitle: 'Admins & managers',
      icon: Shield,
      accent: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
      bar: 'bg-purple-500',
    },
    {
      title: 'Biometric Enrolled',
      value: enrolledCount,
      subtitle: `${total > 0 ? Math.round((enrolledCount / total) * 100) : 0}% neural verified`,
      icon: Fingerprint,
      accent: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
      bar: 'bg-cyan-500',
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 sm:gap-4">
      {items.map((item) => (
        <Card
          key={item.title}
          className="relative overflow-hidden glass bg-gray-900/60 border-gray-800/80 hover:bg-gray-900/90 transition-all rounded-2xl shadow-sm"
        >
          <span className={`absolute left-0 top-0 h-full w-1 rounded-l-xl ${item.bar}`} />
          <CardContent className="p-3.5 sm:p-4 pl-4 sm:pl-5">
            <div className="flex items-center justify-between">
              <div className={`p-2 sm:p-2.5 rounded-xl border ${item.accent}`}>
                <item.icon className="h-4 w-4" />
              </div>
              <span className="text-xl sm:text-2xl font-black text-gray-100 tracking-tight">
                {item.value}
              </span>
            </div>
            <div className="mt-2">
              <p className="text-xs font-bold text-gray-200 truncate">{item.title}</p>
              <p className="text-[10px] text-gray-400 mt-0.5 truncate">{item.subtitle}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default DirectorySummary;
