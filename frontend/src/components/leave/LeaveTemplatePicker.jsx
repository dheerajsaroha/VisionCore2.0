import React, { useState, useEffect, useCallback } from 'react';
import {
  Sparkles, Check, Loader2, MapPin, AlertTriangle, Layers, ChevronDown
} from 'lucide-react';
import { leaveService } from '../../services/leaveService';
import { Button } from '../ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { useToast } from '../ui/Toast';

const ACCENT = {
  IN: 'border-amber-500/30 bg-amber-500/5',
  UK: 'border-blue-500/30 bg-blue-500/5',
  US: 'border-emerald-500/30 bg-emerald-500/5',
};

/**
 * LeaveTemplatePicker — lets an organization choose its starting set of leave
 * types.
 *
 * These were previously a fixed six-item list pushed into every tenant on first
 * access, so a design studio and a hospital both received 180 days of maternity
 * leave. Which leave an organization offers is a business decision that varies
 * by sector and region, so the choice is made here instead of in code.
 */
export function LeaveTemplatePicker({ onApplied }) {
  const toast = useToast?.();
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [confirmReplace, setConfirmReplace] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await leaveService.getTemplates();
      setTemplates(Array.isArray(data) ? data : []);
    } catch {
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const apply = async (template, replace) => {
    setApplying(template.code);
    try {
      const { data } = await leaveService.applyTemplate(template.code, replace);
      const parts = [];
      if (data.created?.length) parts.push(`${data.created.length} added`);
      if (data.updated?.length) parts.push(`${data.updated.length} updated`);
      if (data.deactivated?.length) parts.push(`${data.deactivated.length} deactivated`);
      toast?.({
        message: `${template.name} applied${parts.length ? ` — ${parts.join(', ')}` : ''}.`,
        type: 'success',
        duration: 5000,
      });
      setConfirmReplace(null);
      setExpanded(null);
      await load();
      onApplied?.();
    } catch (err) {
      toast?.({
        message: err.response?.data?.detail || 'Could not apply that template.',
        type: 'error',
        duration: 5000,
      });
    } finally {
      setApplying(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-12 text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading templates…
      </div>
    );
  }

  return (
    <Card className="border border-slate-800 bg-slate-900/90 shadow-xl">
      <CardHeader className="border-b border-slate-800">
        <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-indigo-400" />
          Start from a Template
        </CardTitle>
        <p className="text-sm text-slate-400 mt-1">
          Pick the leave types that suit your organization. Existing types are
          kept — applying a template only adds what you are missing.
        </p>
      </CardHeader>

      <CardContent className="pt-6 space-y-3">
        {templates.length === 0 && (
          <p className="text-sm text-slate-500 py-6 text-center">
            No templates are available. Create leave types directly instead.
          </p>
        )}

        {templates.map((t) => {
          const isOpen = expanded === t.code;
          const needsConfirm = confirmReplace === t.code;

          return (
            <div
              key={t.code}
              className={`rounded-xl border transition ${ACCENT[t.region] || 'border-slate-800 bg-slate-900/50'}`}
            >
              <button
                type="button"
                onClick={() => setExpanded(isOpen ? null : t.code)}
                className="w-full flex items-start gap-3 p-4 text-left"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-white">{t.name}</span>
                    {t.region && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-bold text-slate-300">
                        <MapPin className="h-2.5 w-2.5" />
                        {t.region}
                      </span>
                    )}
                    {t.is_default && (
                      <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 text-[10px] font-bold text-indigo-300">
                        SUGGESTED
                      </span>
                    )}
                    <span className="text-xs text-slate-500">
                      {t.item_count} type{t.item_count === 1 ? '' : 's'}
                    </span>
                  </div>
                  {t.description && (
                    <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
                      {t.description}
                    </p>
                  )}
                </div>
                <ChevronDown
                  className={`h-5 w-5 shrink-0 text-slate-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                />
              </button>

              {isOpen && (
                <div className="border-t border-slate-800/70 px-4 pb-4 pt-3">
                  <ul className="space-y-1.5">
                    {t.items.map((item) => (
                      <li
                        key={item.code}
                        className="flex items-baseline justify-between gap-3 rounded-lg bg-slate-950/40 px-3 py-2"
                      >
                        <span className="min-w-0">
                          <span className="text-sm text-slate-200">{item.name}</span>
                          {item.gender_specific && (
                            <span className="ml-2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-400">
                              {item.gender_specific}
                            </span>
                          )}
                          {!item.is_paid && (
                            <span className="ml-2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-400">
                              Unpaid
                            </span>
                          )}
                        </span>
                        <span className="shrink-0 text-xs font-semibold text-slate-400">
                          {item.max_days_per_year > 0 ? `${item.max_days_per_year} days/yr` : 'Uncapped'}
                        </span>
                      </li>
                    ))}
                  </ul>

                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <Button
                      size="sm"
                      onClick={() => apply(t, false)}
                      isLoading={applying === t.code}
                    >
                      <Check className="h-4 w-4" />
                      Add missing types
                    </Button>

                    {t.already_configured && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setConfirmReplace(needsConfirm ? null : t.code)}
                      >
                        Re-align to this template
                      </Button>
                    )}
                  </div>

                  {t.already_configured && (
                    <p className="mt-2 flex items-start gap-1.5 text-[11px] text-slate-500">
                      <Layers className="h-3 w-3 mt-0.5 shrink-0" />
                      You already have types from this template.
                    </p>
                  )}

                  {needsConfirm && (
                    <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
                      <p className="flex items-start gap-2 text-xs text-amber-200">
                        <AlertTriangle className="h-4 w-4 shrink-0" />
                        <span>
                          Re-aligning overwrites the rules on types from this
                          template and <strong>deactivates</strong> any of your
                          types it does not contain. No type is deleted, but
                          employees can no longer request a deactivated one.
                        </span>
                      </p>
                      <div className="mt-3 flex gap-2">
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => apply(t, true)}
                          isLoading={applying === t.code}
                        >
                          Re-align
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setConfirmReplace(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export default LeaveTemplatePicker;
