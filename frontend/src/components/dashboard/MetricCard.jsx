/**
 * MetricCard.jsx
 * Reusable KPI & Metric Card with accent indicators, trend tags, and theme-aware tokens.
 */
import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { Card, CardContent } from '../ui/Card';
import { Skeleton } from '../ui/Skeleton';
import { cn } from '../../lib/utils';

const accentStyles = {
  indigo: {
    bar: 'bg-indigo-500',
    iconBg: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
    text: 'text-indigo-400',
  },
  emerald: {
    bar: 'bg-emerald-500',
    iconBg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    text: 'text-emerald-400',
  },
  amber: {
    bar: 'bg-amber-500',
    iconBg: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    text: 'text-amber-400',
  },
  rose: {
    bar: 'bg-rose-500',
    iconBg: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    text: 'text-rose-400',
  },
  purple: {
    bar: 'bg-purple-500',
    iconBg: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    text: 'text-purple-400',
  },
  blue: {
    bar: 'bg-blue-500',
    iconBg: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    text: 'text-blue-400',
  },
  cyan: {
    bar: 'bg-cyan-500',
    iconBg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
    text: 'text-cyan-400',
  },
};

export function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  accent = 'indigo',
  trend,
  trendLabel,
  loading = false,
  onClick,
  className,
}) {
  if (loading) {
    return (
      <Card className="border-slate-800/80 bg-slate-900/60 p-5">
        <div className="flex items-center justify-between">
          <Skeleton className="h-10 w-10 rounded-xl bg-slate-800" />
          <Skeleton className="h-5 w-16 rounded-full bg-slate-800" />
        </div>
        <div className="mt-4 space-y-2">
          <Skeleton className="h-7 w-24 bg-slate-800" />
          <Skeleton className="h-4 w-32 bg-slate-800/60" />
        </div>
      </Card>
    );
  }

  const style = accentStyles[accent] || accentStyles.indigo;

  return (
    <Card
      className={cn(
        "relative overflow-hidden group h-full border-slate-800/80 bg-slate-900/60 hover:bg-slate-900/90 transition-all duration-300 shadow-lg",
        onClick && "cursor-pointer hover:border-slate-700",
        className
      )}
      onClick={onClick}
    >
      <span className={cn("absolute left-0 top-0 h-full w-1 rounded-l-xl", style.bar)} />
      <CardContent className="p-5 pl-6">
        <div className="flex items-start justify-between">
          {Icon && (
            <div className={cn("p-2.5 rounded-xl border transition-transform duration-300 group-hover:scale-105", style.iconBg)}>
              <Icon className="h-5 w-5" />
            </div>
          )}

          {trend !== undefined && (
            <div className={cn(
              "flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border",
              trend >= 0
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : "bg-rose-500/10 text-rose-400 border-rose-500/20"
            )}>
              {trend >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              <span>{trend >= 0 ? '+' : ''}{trend}%</span>
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
          {subtitle && (
            <p className="text-[11px] text-slate-500 mt-0.5 font-medium">
              {subtitle}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
