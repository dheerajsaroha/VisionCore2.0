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

    if (error.response?.status === 403) {
      const data = error.response?.data;
      let detail = 'You do not have permission to access this resource.';
      let errorCode = 'PERMISSION_DENIED';

      if (data && typeof data === 'object') {
        detail = data.detail || data.message || detail;
        errorCode = data.code || errorCode;
      } else if (typeof data === 'string') {
        detail = data;
      }

      console.error(`Forbidden [${errorCode}]:`, detail);
      window.dispatchEvent(new CustomEvent('app:forbidden', { detail: { code: errorCode, message: detail } }));
    }

    return Promise.reject(error);
  }
);

export default apiClient;
