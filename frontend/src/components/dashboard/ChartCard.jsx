/**
 * ChartCard.jsx
 * Reusable wrapper component for enterprise charts and graphical widgets.
 */
import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { cn } from '../../lib/utils';

export function ChartCard({
  title,
  subtitle,
  icon: Icon,
  badge,
  headerControls,
  loading = false,
  empty = false,
  emptyMessage = 'No chart data available for this range.',
  emptyAction,
  chartHeight = 'h-64',
  children,
  className,
  contentClassName = 'p-6',
}) {
  if (loading) {
    return (
      <Card className={cn('border-slate-800/80 bg-slate-900/60 shadow-xl overflow-hidden', className)}>
        <CardHeader className="border-b border-slate-800/60 pb-4">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Skeleton className="h-5 w-44 bg-slate-800" />
              <Skeleton className="h-3.5 w-60 bg-slate-800/60" />
            </div>
            <Skeleton className="h-8 w-28 bg-slate-800" />
          </div>
        </CardHeader>
        <CardContent className="p-6">
          <Skeleton className={cn('w-full bg-slate-800/40 rounded-xl', chartHeight)} />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn('border-slate-800/80 bg-slate-900/60 shadow-xl overflow-hidden', className)}>
      <CardHeader className="border-b border-slate-800/60 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start sm:items-center gap-2.5">
            {Icon && (
              <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shrink-0">
                <Icon className="h-4 w-4" />
              </div>
            )}
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <CardTitle className="text-slate-100 text-base font-bold tracking-tight">
                  {title}
                </CardTitle>
                {badge}
              </div>
              {subtitle && (
                <CardDescription className="text-slate-400 text-xs mt-0.5">
                  {subtitle}
                </CardDescription>
              )}
            </div>
          </div>

          {headerControls && <div className="shrink-0">{headerControls}</div>}
        </div>
      </CardHeader>

      <CardContent className={contentClassName}>
        {empty ? (
          <div className="py-8">
            <EmptyState
              title="No Data"
              description={emptyMessage}
              action={emptyAction}
            />
          </div>
        ) : (
          <div className={chartHeight}>{children}</div>
        )}
      </CardContent>
    </Card>
  );
}
export default ChartCard;
