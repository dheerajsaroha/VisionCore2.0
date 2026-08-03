import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authService } from '../services/authService';

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      isHydrated: false,

login: async (email, password) => {
        set({ isLoading: true });
        try {
          const response = await authService.login(email, password);
          const { access_token, refresh_token } = response.data;
          
          // 🐛 FIX: Save token to store FIRST so apiClient interceptor picks it up
          // from localStorage (via Zustand persist middleware) before getMe call
          set({ token: access_token, refreshToken: refresh_token });
          
          // Fetch user profile immediately after login
          const meResponse = await authService.getMe(access_token);
          
          set({
            user: meResponse.data,
            isAuthenticated: true,
            isLoading: false,
          });
          return true;
        } catch (error) {
          set({ isLoading: false, token: null, refreshToken: null, isAuthenticated: false, user: null });
          throw error;
        }
      },

      logout: async () => {
        try {
          const { token } = get();
          if (token) {
            await authService.logout(token);
          }
        } catch {
          // Ignore logout errors
        } finally {
          set({
            user: null,
            token: null,
            refreshToken: null,
            isAuthenticated: false,
            isLoading: false,
          });
          localStorage.removeItem('auth-storage');
        }
      },

      setToken: (token) => set({ token }),
      setRefreshToken: (refreshToken) => set({ refreshToken }),

      refreshAccessToken: async () => {
        const { refreshToken } = get();
        if (!refreshToken) {
          get().logout();
          throw new Error('No refresh token available');
        }
        try {
          const response = await authService.refreshToken(refreshToken);
          set({ token: response.data.access_token, isAuthenticated: true });
          return response.data.access_token;
        } catch (error) {
          get().logout();
          throw error;
        }
      },

      refreshProfile: async () => {
        const { token } = get();
        if (!token) return null;
        try {
          const res = await authService.getMe(token);
          set({ user: res.data });
          return res.data;
        } catch (error) {
          console.error("Failed reactive profile refresh:", error);
          return null;
        }
      },

      hydrate: () => {
        const state = get();
        if (state.token && !state.user) {
          // Try to restore user from token
          authService
            .getMe(state.token)
            .then((res) => {
              set({ user: res.data, isAuthenticated: true, isHydrated: true });
            })
            .catch(() => {
              // Token invalid or expired — clear auth state completely
              set({
                user: null,
                token: null,
                refreshToken: null,
                isAuthenticated: false,
                isHydrated: true,
              });
              localStorage.removeItem('auth-storage');
            });
        } else {
          set({ isHydrated: true });
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

