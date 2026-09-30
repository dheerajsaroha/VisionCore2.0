import apiClient from './apiClient';

/**
 * Download a file returned by an authenticated endpoint.
 *
 * The shared apiClient attaches the bearer token to JSON requests, but a plain
 * `window.open` or anchor download cannot, so the server would answer 401. This
 * fetches the blob with the token and triggers a save from the object URL.
 */
const downloadBlob = async (url, filename) => {
  const response = await apiClient.get(url, { responseType: 'blob' });
  const blobUrl = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoke on the next tick so the navigation has already started.
  setTimeout(() => URL.revokeObjectURL(blobUrl), 0);
  return response.data;
};

export const payrollService = {
  getPayrolls: (month, year) =>
    apiClient.get('/payroll/', { params: { month, year } }),

  generatePayroll: (month, year) =>
    apiClient.post('/payroll/generate', { month, year }),

  updatePayrollStatus: (payrollId, statusUpdate) =>
    apiClient.patch(`/payroll/${payrollId}`, statusUpdate),

  // ── Self-service ─────────────────────────────────────────────────────
  /** The signed-in employee's own payslips, newest period first. */
  getMyPayslips: () => apiClient.get('/payroll/me/payslips'),

  /** Payslip metadata, generating the PDF on first access. */
  getPayslip: (payrollId) => apiClient.get(`/payroll/${payrollId}/payslip`),

  /** Download the payslip PDF. */
  downloadPayslip: (payrollId, filename) =>
    downloadBlob(`/payroll/${payrollId}/payslip/download`, filename || `payslip-${payrollId}.pdf`),
};
