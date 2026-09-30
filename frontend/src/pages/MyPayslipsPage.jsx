import React, { useState, useEffect, useCallback } from 'react';
import {
  Wallet, Download, RefreshCw, Loader2, Receipt, CalendarDays
} from 'lucide-react';
import { payrollService } from '../services/payrollService';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const STATUS_STYLES = {
  paid: 'bg-emerald-500/10 text-emerald-400',
  pending: 'bg-amber-500/10 text-amber-400',
  draft: 'bg-gray-500/10 text-gray-400',
};

const formatMoney = (amount, currency = 'INR') => {
  const value = Number(amount ?? 0);
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(value);
  } catch {
    // An unknown code should not blank out the figure.
    return `${currency} ${value.toFixed(2)}`;
  }
};

export default function MyPayslipsPage() {
  const [payslips, setPayslips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [downloadingId, setDownloadingId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await payrollService.getMyPayslips();
      setPayslips(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Could not load your payslips. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDownload = async (row) => {
    setDownloadingId(row.payroll_id);
    setError('');
    try {
      await payrollService.downloadPayslip(
        row.payroll_id,
        `payslip-${row.year}-${String(row.month).padStart(2, '0')}.pdf`
      );
    } catch (err) {
      setError(
        err.response?.data?.detail || 'Could not download the payslip. Please try again.'
      );
    } finally {
      setDownloadingId(null);
    }
  };

  const latest = payslips[0];
  const yearTotalNet = payslips.reduce((sum, p) => sum + Number(p.total_salary || 0), 0);
  const yearCurrency = latest?.currency || 'INR';

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-indigo-500/15 p-3">
              <Wallet className="h-7 w-7 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">My Payslips</h1>
              <p className="mt-1 text-sm text-gray-400">
                Download your payslips for any period
              </p>
            </div>
          </div>
          <Button variant="secondary" onClick={load} isLoading={loading}>
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        </div>
      </section>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Payslips
          </p>
          <p className="mt-2 text-3xl font-bold text-white">{payslips.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Latest Net Pay
          </p>
          <p className="mt-2 text-3xl font-bold text-emerald-400">
            {latest ? formatMoney(latest.total_salary, latest.currency) : '—'}
          </p>
          {latest && (
            <p className="mt-1 text-xs text-gray-500">
              {MONTHS[latest.month - 1]} {latest.year}
            </p>
          )}
        </Card>
        <Card className="p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Total Net Pay
          </p>
          <p className="mt-2 text-3xl font-bold text-indigo-400">
            {payslips.length ? formatMoney(yearTotalNet, yearCurrency) : '—'}
          </p>
          <p className="mt-1 text-xs text-gray-500">Across all periods</p>
        </Card>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="border-b border-gray-800 px-6 py-5">
          <h2 className="text-lg font-semibold text-white">Payslip History</h2>
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-3 px-6 py-16 text-gray-400">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading your payslips…
          </div>
        ) : payslips.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <Receipt className="mx-auto h-10 w-10 text-gray-600" />
            <p className="mt-3 text-sm text-gray-400">No payslips yet</p>
            <p className="mt-1 text-xs text-gray-500">
              Payslips appear here once payroll has been run for a period you were
              part of.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-gray-800 text-xs uppercase tracking-wider text-gray-500">
                <tr>
                  <th className="px-6 py-3 font-semibold">Period</th>
                  <th className="px-6 py-3 font-semibold">Status</th>
                  <th className="px-6 py-3 font-semibold">Base</th>
                  <th className="px-6 py-3 font-semibold">Deductions</th>
                  <th className="px-6 py-3 font-semibold">Net Pay</th>
                  <th className="px-6 py-3 text-right font-semibold">Payslip</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {payslips.map((row) => (
                  <tr key={row.payroll_id} className="hover:bg-gray-800/40">
                    <td className="whitespace-nowrap px-6 py-4 font-medium text-white">
                      <span className="flex items-center gap-2">
                        <CalendarDays className="h-4 w-4 text-gray-500" />
                        {MONTHS[row.month - 1]} {row.year}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${
                          STATUS_STYLES[row.status] || STATUS_STYLES.draft
                        }`}
                      >
                        {row.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-gray-300">
                      {formatMoney(row.base_salary, row.currency)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-red-400">
                      {formatMoney(row.deductions, row.currency)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 font-semibold text-emerald-400">
                      {formatMoney(row.total_salary, row.currency)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleDownload(row)}
                        isLoading={downloadingId === row.payroll_id}
                      >
                        <Download className="h-4 w-4" /> PDF
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
