import React, { useState, useEffect, useCallback } from 'react';
import { Settings2, Loader2, Save, Info, RotateCcw } from 'lucide-react';
import { leaveService } from '../../services/leaveService';
import { Button } from '../ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { useToast } from '../ui/Toast';

const ACCRUAL_HELP = {
  annual_grant: 'The full entitlement is granted at the start of the year.',
  monthly_accrual: 'The entitlement is earned evenly across the year, so joining mid-year earns a pro-rata amount.',
  per_payroll: 'The entitlement is granted each payroll cycle.',
  unlimited: 'Leave is never capped and never runs out, for people who should not track a balance.',
};

const LABEL = 'block text-xs font-semibold text-slate-300 mb-1.5';

const numField = (value, onChange, attrs) => (
  <input
    type="number"
    value={value}
    onChange={(e) => onChange(e.target.value)}
    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
    {...attrs}
  />
);

/**
 * LeavePolicyEditor — the organization's leave rules for one year.
 *
 * A policy is scoped to a single policy year on purpose. A year with no row
 * falls back to the defaults rather than inheriting the previous year, because
 * entitlements granted last year are not this year's rules.
 */
export function LeavePolicyEditor() {
  const toast = useToast?.();
  const [policy, setPolicy] = useState(null);
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await leaveService.getPolicy();
      setPolicy(data);
      setForm({
        name: data.name ?? '',
        accrual_type: data.accrual_type,
        allow_negative_balance: !!data.allow_negative_balance,
        auto_approve_after_days:
          data.auto_approve_after_days === null || data.auto_approve_after_days === undefined
            ? ''
            : String(data.auto_approve_after_days),
        config: { ...data.config },
      });
    } catch {
      setPolicy(null);
      setForm(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const setConfig = (key, value) =>
    setForm((f) => ({ ...f, config: { ...f.config, [key]: value } }));

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const autoApprove =
        form.auto_approve_after_days === '' ? null : Number(form.auto_approve_after_days);

      const { data } = await leaveService.savePolicy({
        name: form.name.trim() || 'Default',
        accrual_type: form.accrual_type,
        allow_negative_balance: form.allow_negative_balance,
        auto_approve_after_days: autoApprove,
        policy_config: {
          probation_days: Number(form.config.probation_days) || 0,
          day_rounding: Number(form.config.day_rounding) || 0.5,
          apply_carry_forward: !!form.config.apply_carry_forward,
          allow_half_day: !!form.config.allow_half_day,
          allow_exceeding_per_request: !!form.config.allow_exceeding_per_request,
        },
      });
      setPolicy(data);
      toast?.({ message: 'Leave policy saved.', type: 'success' });
      await load();
    } catch (err) {
      toast?.({
        message: err.response?.data?.detail || 'Could not save the leave policy.',
        type: 'error',
        duration: 5000,
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-12 text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading policy…
      </div>
    );
  }

  if (!form) {
    return (
      <Card className="border border-slate-800 bg-slate-900/90">
        <CardContent className="pt-6">
          <p className="text-sm text-slate-500">
            The leave policy could not be loaded.
          </p>
        </CardContent>
      </Card>
    );
  }

  const cfg = form.config;

  return (
    <Card className="border border-slate-800 bg-slate-900/90 shadow-xl">
      <CardHeader className="border-b border-slate-800">
        <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
          <Settings2 className="h-5 w-5 text-indigo-400" />
          Leave Policy
        </CardTitle>
        <p className="text-sm text-slate-400 mt-1">
          These rules apply to {policy.policy_year} and every leave request your
          team makes.
        </p>
      </CardHeader>

      <form onSubmit={save}>
        <CardContent className="pt-6 space-y-6">
          {policy.is_default && (
            <div className="flex items-start gap-2 rounded-lg border border-slate-700 bg-slate-950/60 p-3">
              <Info className="h-4 w-4 shrink-0 text-slate-400" />
              <p className="text-xs text-slate-400">
                You are on the default policy. Save to make these rules your
                own — defaults change as the product improves, saved rules do
                not.
              </p>
            </div>
          )}

          <div>
            <label className={LABEL}>Policy name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className={LABEL}>How leave is granted</label>
            <div className="space-y-2">
              {(policy.available_accrual_types || []).map((opt) => (
                <label
                  key={opt}
                  className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition ${
                    form.accrual_type === opt
                      ? 'border-indigo-500 bg-indigo-500/10'
                      : 'border-slate-700 bg-slate-950/40 hover:border-slate-600'
                  }`}
                >
                  <input
                    type="radio"
                    name="accrual_type"
                    value={opt}
                    checked={form.accrual_type === opt}
                    onChange={(e) => setForm((f) => ({ ...f, accrual_type: e.target.value }))}
                    className="mt-1 h-4 w-4 accent-indigo-500"
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-white">
                      {opt.replace(/_/g, ' ')}
                    </span>
                    <span className="block text-xs text-slate-400">
                      {ACCRUAL_HELP[opt]}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-950/40 p-4">
            <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Rules
            </p>

            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={form.allow_negative_balance}
                onChange={(e) =>
                  setForm((f) => ({ ...f, allow_negative_balance: e.target.checked }))
                }
                className="mt-0.5 h-4 w-4 accent-indigo-500"
              />
              <span>
                <span className="block text-sm text-slate-200">
                  Allow negative balances
                </span>
                <span className="block text-xs text-slate-400">
                  Employees may take more leave than they have accrued, and go
                  into arrears. Turn this off to block requests that exceed the
                  balance.
                </span>
              </span>
            </label>

            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={cfg.apply_carry_forward}
                onChange={(e) => setConfig('apply_carry_forward', e.target.checked)}
                className="mt-0.5 h-4 w-4 accent-indigo-500"
              />
              <span>
                <span className="block text-sm text-slate-200">
                  Carry unused leave into next year
                </span>
                <span className="block text-xs text-slate-400">
                  Applied when the leave year rolls over.
                </span>
              </span>
            </label>

            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={cfg.allow_half_day}
                onChange={(e) => setConfig('allow_half_day', e.target.checked)}
                className="mt-0.5 h-4 w-4 accent-indigo-500"
              />
              <span>
                <span className="block text-sm text-slate-200">Allow half days</span>
                <span className="block text-xs text-slate-400">
                  Employees may request half-day leave.
                </span>
              </span>
            </label>

            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={cfg.allow_exceeding_per_request}
                onChange={(e) =>
                  setConfig('allow_exceeding_per_request', e.target.checked)
                }
                className="mt-0.5 h-4 w-4 accent-indigo-500"
              />
              <span>
                <span className="block text-sm text-slate-200">
                  Allow exceeding a per-request cap
                </span>
                <span className="block text-xs text-slate-400">
                  Waives the single-request limit on each leave type. The
                  per-year cap is always enforced.
                </span>
              </span>
            </label>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className={LABEL}>Probation days</label>
              {numField(cfg.probation_days, (v) => setConfig('probation_days', v), {
                min: 0,
                max: 365,
              })}
              <p className="mt-1 text-[11px] text-slate-500">
                Days after joining before leave starts accruing.
              </p>
            </div>

            <div>
              <label className={LABEL}>Day rounding</label>
              {numField(cfg.day_rounding, (v) => setConfig('day_rounding', v), {
                min: 0.25,
                max: 1,
                step: 0.25,
              })}
              <p className="mt-1 text-[11px] text-slate-500">
                How partial days are rounded.
              </p>
            </div>

            <div>
              <label className={LABEL}>Auto-approve under (days)</label>
              {numField(form.auto_approve_after_days, (v) =>
                setForm((f) => ({ ...f, auto_approve_after_days: v })), {
                min: 0,
                max: 30,
                placeholder: 'Never',
              })}
              <p className="mt-1 text-[11px] text-slate-500">
                Short requests skip manual approval. Leave blank for none.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 border-t border-slate-800 pt-4">
            <Button type="submit" isLoading={saving}>
              <Save className="h-4 w-4" /> Save policy
            </Button>
            <Button type="button" variant="ghost" onClick={load}>
              <RotateCcw className="h-4 w-4" /> Discard changes
            </Button>
          </div>
        </CardContent>
      </form>
    </Card>
  );
}

export default LeavePolicyEditor;
