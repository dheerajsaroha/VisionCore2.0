/**
 * Client for the offer letter endpoints.
 *
 * The application endpoint reports `candidate_name` and `job_title` but not
 * `candidate_id`, so callers that need to attach an offer to a specific
 * application pass it explicitly.
 */
const BASE = '/api/v1/recruitment/offer-letters';

async function request(path, { method = 'GET', body, token } = {}) {
  const response = await fetch(path, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const detail = await response.json();
      // The generate endpoint reports unresolved merge tags as an object.
      message =
        typeof detail?.detail === 'string'
          ? detail.detail
          : detail?.detail?.error || message;
    } catch {
      // Non-JSON error body; keep the status-based message.
    }
    throw new Error(message);
  }

  if (response.status === 204) return null;
  return response.json();
}

export const offerLetterService = {
  list: (token, params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null && v !== '')
    ).toString();
    return request(`${BASE}${query ? `?${query}` : ''}`, { token });
  },

  get: (offerId, token) => request(`${BASE}/${offerId}`, { token }),

  createOffer: (payload, token) => request(BASE, { method: 'POST', body: payload, token }),

  generate: (offerId, token) =>
    request(`${BASE}/${offerId}/generate`, { method: 'POST', token }),

  send: (offerId, token) => request(`${BASE}/${offerId}/send`, { method: 'POST', token }),

  respond: (offerId, accepted, token, reason) =>
    request(`${BASE}/${offerId}/respond`, {
      method: 'POST',
      body: { accepted, reason },
      token,
    }),

  withdraw: (offerId, token) =>
    request(`${BASE}/${offerId}/withdraw`, { method: 'POST', token }),

  listTags: (token) => request('/api/v1/recruitment/offer-templates/tags', { token }),

  /**
   * Download through fetch so the Authorization header is sent; a plain
   * window.open or anchor href would omit it and receive a 401.
   */
  download: async (offerId, token) => {
    const response = await fetch(`${BASE}/${offerId}/download`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      throw new Error(`Could not download the offer letter (${response.status})`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `offer-${offerId}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },

  downloadUrl: (offerId, token) => offerLetterService.download(offerId, token),
};
