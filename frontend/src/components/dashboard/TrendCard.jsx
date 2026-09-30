/**
 * TrendCard.jsx
 * Reusable metric card highlighting percentage trajectories, positive/negative delta badges,
 * and contextual descriptions.
 */
import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card, CardContent } from '../ui/Card';
import { Skeleton } from '../ui/Skeleton';
import { cn } from '../../lib/utils';

export function TrendCard({
  title,
  value,
  previousValue,
  delta,
  deltaType = 'percentage', // 'percentage' | 'number'
  timeframe = 'vs last month',
  icon: Icon,
  accent = 'indigo',
  loading = false,
  onClick,
  className,
}) {
  if (loading) {
    return (
      <Card className="border-slate-800/80 bg-slate-900/60 p-5">
        <div className="flex items-center justify-between">
          <Skeleton className="h-9 w-9 rounded-xl bg-slate-800" />
          <Skeleton className="h-5 w-16 rounded-full bg-slate-800" />
        </div>
        <div className="mt-4 space-y-2">
          <Skeleton className="h-8 w-24 bg-slate-800" />
          <Skeleton className="h-4 w-32 bg-slate-800/60" />
        </div>
      </Card>
    );
  }

  const isPositive = delta > 0;
  const isNeutral = delta === 0 || delta === undefined;

  const accentStyles = {
    indigo: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    rose: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
    cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
  };

  const currentAccent = accentStyles[accent] || accentStyles.indigo;

  return (
    <Card
      className={cn(
        'relative overflow-hidden group border-slate-800/80 bg-slate-900/60 hover:bg-slate-900/90 transition-all duration-300 shadow-xl',
        onClick && 'cursor-pointer hover:border-slate-700',
        className
      )}
      onClick={onClick}
    >
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          {Icon && (
            <div className={cn('p-2.5 rounded-xl border transition-transform duration-300 group-hover:scale-105', currentAccent)}>
              <Icon className="h-5 w-5" />
            </div>
          )}

          {!isNeutral && (
            <div
              className={cn(
                'flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border',
                isPositive
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
              )}
            >
              {isPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              <span>
                {isPositive ? '+' : ''}
                {delta}
                {deltaType === 'percentage' ? '%' : ''}
              </span>
            </div>
          )}
          {isNeutral && (
            <div className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border bg-slate-800/60 text-slate-400 border-slate-700">
              <Minus className="h-3 w-3" />
              <span>0%</span>
            </div>
          )}
        </div>

        <div className="mt-4">
          <h3 className="text-2xl sm:text-3xl font-black text-slate-100 tracking-tight">
            {value}
          </h3>
          <p className="text-xs font-semibold text-slate-400 mt-1 uppercase tracking-wider">
            {title}
          </p>
          {(timeframe || previousValue) && (
            <p className="text-[11px] text-slate-500 mt-0.5 font-medium">
              {previousValue ? `${previousValue} ` : ''}
              {timeframe}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
export default TrendCard;
