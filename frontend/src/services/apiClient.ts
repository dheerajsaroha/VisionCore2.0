// Centralized axios instance with JWT interceptor and automatic token refresh
/// <reference types="vite/client" />
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' }
});

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];
let inMemoryAccessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function clearAuthStorage(): void {
  // Access credentials live only in the Zustand in-memory store. The refresh
  // credential is an HttpOnly cookie and cannot be cleared from JavaScript.
}

apiClient.interceptors.request.use((config) => {
  const token = inMemoryAccessToken;
  if (token && !config.headers?.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  config.headers['X-Request-ID'] = Math.random().toString(36).substring(2, 10);
  return config;
}, (error) => Promise.reject(error));

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Never intercept the login or refresh endpoints themselves.
    const isAuthEndpoint =
      originalRequest?.url?.includes('/auth/login') ||
      originalRequest?.url?.includes('/auth/refresh') ||
      originalRequest?.url?.includes('/auth/forgot-password') ||
      originalRequest?.url?.includes('/auth/reset-password');

    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      if (isRefreshing) {
        return new Promise((resolve) => {
          addRefreshSubscriber((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(apiClient(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, null, { withCredentials: true });

        const newAccessToken = response.data.access_token;
        setAccessToken(newAccessToken);
        apiClient.defaults.headers.common['Authorization'] = `Bearer ${newAccessToken}`;
        onTokenRefreshed(newAccessToken);

        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        const status = refreshError.response?.status;
        // 422 from refresh means the cookie is invalid/malformed.
        // Treat it the same as an expired cookie: clear state and redirect.
        if (status === 422) {
          console.warn('Refresh token invalid (422). Clearing session.');
        }
        setAccessToken(null);
        clearAuthStorage();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // A 403 here is only interesting if the caller did not already know it
    // would happen. Gated UI should not attempt the call at all, but a
    // request that races a permission change is an expected outcome, and
    // painting a red toast for it is noise. Callers opt out with
    // `{ suppressForbiddenToast: true }`.
    const suppress = Boolean(error.config as Record<string, unknown> | undefined)
      ?.suppressForbiddenToast;
    if (error.response?.status === 403 && !suppress) {
      const data = error.response?.data;

      const announce = (detail: string, errorCode: string) => {
        // Identify the offending request. Without the URL it is impossible to
        // tell which component produced a denial, and the same generic text can
        // come from a dozen places.
        const method = (error.config as { method?: string } | undefined)?.method?.toUpperCase() ?? 'GET';
        const url = (error.config as { url?: string } | undefined)?.url ?? 'unknown';
        const where = `${method} ${url}`;
        console.error(`Forbidden [${errorCode}] ${where}:`, detail);
        window.dispatchEvent(
          new CustomEvent('app:forbidden', { detail: { code: errorCode, message: detail, source: where } })
        );
      };

      // A `responseType: 'blob'` request hands the interceptor a Blob, and
      // `typeof Blob === 'object'`, so `data.detail` read as undefined and every
      // such denial was reported as the generic "you do not have permission"
      // instead of the real reason. Read the body first.
      if (typeof Blob !== 'undefined' && data instanceof Blob) {
        void data.text().then((text) => {
          let detail = 'You do not have permission to access this resource.';
          let errorCode = 'PERMISSION_DENIED';
          try {
            const parsed = JSON.parse(text);
            detail = parsed?.detail || parsed?.message || detail;
            errorCode = parsed?.code || errorCode;
          } catch {
            // A non-JSON body (e.g. an HTML error page) keeps the generic text.
          }
          announce(detail, errorCode);
        });
      } else {
        let detail = 'You do not have permission to access this resource.';
        let errorCode = 'PERMISSION_DENIED';

        if (data && typeof data === 'object') {
          detail = data.detail || data.message || detail;
          errorCode = data.code || errorCode;
        } else if (typeof data === 'string') {
          detail = data;
        }

        announce(detail, errorCode);
      }
    }

    // 402 means the organization's plan does not include the feature. It is
    // surfaced as a dedicated event so a shell can offer an upgrade path
    // instead of the page rendering the billing message as an error. Silenced
    // the same way as 403, because a module gate should have prevented it.
    if (error.response?.status === 402 && !suppress) {
      const feature = error.response?.headers?.['x-subscription-feature'];
      console.warn(`Feature not available [${feature ?? 'unknown'}]`);
      window.dispatchEvent(
        new CustomEvent('app:feature-unavailable', {
          detail: { feature: feature ?? null, plan: error.response?.headers?.['x-subscription-plan'] ?? null },
        })
      );
    }

    return Promise.reject(error);
  }
);

export default apiClient;
