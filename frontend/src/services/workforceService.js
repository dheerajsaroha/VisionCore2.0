import api from './apiClient';

/**
 * workforceService.js — VisionCore 3.0 Workforce Core Domain API Client
 *
 * Covers all 19 route groups in /api/v1/workforce:
 *   attendance, attendance-devices, attendance-policies, geofence,
 *   leave, shifts, rosters, shift-swaps, workforce-planning, bench,
 *   overtime, holidays, corrections, time-tracking, analytics
 */
export const workforceService = {
  // ──────────────────────────────────────────────────────────────
  // ATTENDANCE
  // ──────────────────────────────────────────────────────────────
  attendance: {
    mark: (data) => api.post('/workforce/attendance/mark', data),
    sessions: (params = {}) => api.get('/workforce/attendance/sessions', { params }),
    timeline: (userId, params = {}) => api.get(`/workforce/attendance/timeline/${userId}`, { params }),
    summary: (params = {}) => api.get('/workforce/attendance/summary', { params }),
    events: (sessionId) => api.get(`/workforce/attendance/events/${sessionId}`),
    evaluatePolicy: (ctx) => api.post('/workforce/attendance/evaluate-policy', ctx),
  },

  // ──────────────────────────────────────────────────────────────
  // ATTENDANCE DEVICES
  // ──────────────────────────────────────────────────────────────
  devices: {
    list: (params = {}) => api.get('/workforce/devices', { params }),
    create: (data) => api.post('/workforce/devices', data),
    update: (id, data) => api.put(`/workforce/devices/${id}`, data),
    deactivate: (id) => api.delete(`/workforce/devices/${id}`),
  },

  // ──────────────────────────────────────────────────────────────
  // ATTENDANCE POLICIES
  // ──────────────────────────────────────────────────────────────
  policies: {
    get: () => api.get('/workforce/policies/attendance'),
    create: (data) => api.post('/workforce/policies/attendance', data),
  },

  // ──────────────────────────────────────────────────────────────
  // GEOFENCE
  // ──────────────────────────────────────────────────────────────
  geofence: {
    list: () => api.get('/workforce/geofence/zones'),
    create: (data) => api.post('/workforce/geofence/zones', data),
    validate: (lat, lng) => api.post('/workforce/geofence/validate', { lat, lng }),
  },

  // ──────────────────────────────────────────────────────────────
  // LEAVE
  // ──────────────────────────────────────────────────────────────
  leave: {
    apply: (data) => api.post('/workforce/leave/apply', data),
    approve: (id, note) => api.post(`/workforce/leave/requests/${id}/approve`, { note }),
    reject: (id, note) => api.post(`/workforce/leave/requests/${id}/reject`, { note }),
    cancel: (id) => api.post(`/workforce/leave/requests/${id}/cancel`),
    requests: (params = {}) => api.get('/workforce/leave/requests', { params }),
    balances: (params = {}) => api.get('/workforce/leave/balance', { params }),
    types: (params = {}) => api.get('/workforce/leave/types', { params }),
    runAccrual: (data) => api.post('/workforce/leave/accrual/run', data),
    calculateEncashment: (data) => api.post('/workforce/leave/encashment/calculate', data),
  },

  // ──────────────────────────────────────────────────────────────
  // SHIFTS
  // ──────────────────────────────────────────────────────────────
  shifts: {
    templates: (activeOnly = true) => api.get('/workforce/shifts/templates', { params: { active_only: activeOnly } }),
    createTemplate: (data) => api.post('/workforce/shifts/templates', data),
    updateTemplate: (id, data) => api.put(`/workforce/shifts/templates/${id}`, data),
    legacyList: (params = {}) => api.get('/workforce/shifts/legacy', { params }),
    createLegacy: (data) => api.post('/workforce/shifts/legacy', data),
    assignments: (params = {}) => api.get('/workforce/shifts/assignments', { params }),
    assign: (data) => api.post('/workforce/shifts/assignments', data),
    swaps: (params = {}) => api.get('/workforce/shift-swaps', { params }),
    createSwap: (data) => api.post('/workforce/shift-swaps', data),
    resolveSwap: (id, data) => api.post(`/workforce/shift-swaps/${id}/resolve`, data),
  },

  // ──────────────────────────────────────────────────────────────
  // ROSTERS
  // ──────────────────────────────────────────────────────────────
  rosters: {
    list: (params = {}) => api.get('/workforce/rosters', { params }),
    create: (data) => api.post('/workforce/rosters', data),
    publish: (id) => api.post(`/workforce/rosters/${id}/publish`),
    entries: (rosterId) => api.get(`/workforce/rosters/${rosterId}/entries`),
  },

  // ──────────────────────────────────────────────────────────────
  // WORKFORCE PLANNING
  // ──────────────────────────────────────────────────────────────
  planning: {
    headcount: (params = {}) => api.get('/workforce/planning/headcount', { params }),
    createHeadcount: (data) => api.post('/workforce/planning/headcount', data),
    vacancies: (params = {}) => api.get('/workforce/planning/vacancies', { params }),
    forecasts: (params = {}) => api.get('/workforce/planning/forecasts', { params }),
    createForecast: (data) => api.post('/workforce/planning/forecasts', data),
    capacitySnapshot: (data = {}) => api.post('/workforce/planning/capacity/snapshot', data),
    capacity: (params = {}) => api.get('/workforce/planning/capacity', { params }),
  },

  // ──────────────────────────────────────────────────────────────
  // BENCH MANAGEMENT
  // ──────────────────────────────────────────────────────────────
  bench: {
    list: (params = {}) => api.get('/workforce/bench', { params }),
    add: (data) => api.post('/workforce/bench', data),
    release: (userId) => api.post(`/workforce/bench/${userId}/release`),
    agingReport: () => api.get('/workforce/bench/aging-report'),
  },

  // ──────────────────────────────────────────────────────────────
  // OVERTIME
  // ──────────────────────────────────────────────────────────────
  overtime: {
    compute: (data) => api.post('/workforce/overtime/compute', data),
    list: (params = {}) => api.get('/workforce/overtime', { params }),
    approve: (id, note) => api.post(`/workforce/overtime/${id}/approve`, { note }),
    reject: (id, note) => api.post(`/workforce/overtime/${id}/reject`, { note }),
    compOff: {
      list: (params = {}) => api.get('/workforce/overtime/comp-off', { params }),
    },
  },

  // ──────────────────────────────────────────────────────────────
  // HOLIDAYS
  // ──────────────────────────────────────────────────────────────
  holidays: {
    calendars: () => api.get('/workforce/holidays/calendars'),
    createCalendar: (data) => api.post('/workforce/holidays/calendars', data),
    entries: (params = {}) => api.get('/workforce/holidays/entries', { params }),
    addEntry: (calendarId, data) => api.post(`/workforce/holidays/calendars/${calendarId}/entries`, data),
  },

  // ──────────────────────────────────────────────────────────────
  // ATTENDANCE CORRECTIONS
  // ──────────────────────────────────────────────────────────────
  corrections: {
    list: (params = {}) => api.get('/workforce/corrections', { params }),
    create: (data) => api.post('/workforce/corrections', data),
    approve: (id, note) => api.post(`/workforce/corrections/${id}/approve`, { note }),
    reject: (id, note) => api.post(`/workforce/corrections/${id}/reject`, { note }),
  },

  // ──────────────────────────────────────────────────────────────
  // TIME TRACKING
  // ──────────────────────────────────────────────────────────────
  time: {
    clockIn: (data) => api.post('/workforce/time/clock-in', data),
    clockOut: (data) => api.post('/workforce/time/clock-out', data),
    breakStart: (data) => api.post('/workforce/time/break/start', data),
    breakEnd: (data) => api.post('/workforce/time/break/end', data),
    entries: (params = {}) => api.get('/workforce/time/entries', { params }),
    approve: (entryId, note) => api.post(`/workforce/time/entries/${entryId}/approve`, { note }),
  },

  // ──────────────────────────────────────────────────────────────
  // ANALYTICS
  // ──────────────────────────────────────────────────────────────
  analytics: {
    dashboard: (params = {}) => api.get('/workforce/analytics/dashboard', { params }),
    trends: (params = {}) => api.get('/workforce/analytics/trends', { params }),
    byDepartment: (params = {}) => api.get('/workforce/analytics/by-department', { params }),
  },
};

export default workforceService;
