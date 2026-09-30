import { create } from 'zustand';
import { authService } from '../services/authService';
import { setAccessToken } from '../services/apiClient';
import { usePermissionStore } from './permissionStore';

export const useAuthStore = create(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      isHydrated: false,
      authorizationInitialized: false,
      sessionEpoch: 0,

      initializeAuthorization: async () => {
        // Both authorization dimensions must be resolved before the app is
        // allowed to render gated UI: the RBAC permissions and the plan
        // features. Resolving only permissions left a window where
        // `authorizationInitialized` was true but the feature set was still
        // empty, so every feature-gated module read as "not in your plan".
        const [{ usePermissionStore: permStore }, { useSubscriptionStore: subStore }] =
          await Promise.all([import('./permissionStore'), import('./subscriptionStore')]);

        const [permissions] = await Promise.allSettled([
          permStore.getState().fetchMyPermissions(),
          subStore.getState().fetchMySubscription(),
        ]);
        set({ authorizationInitialized: true });
        return permissions.status === 'fulfilled' ? permissions.value : null;
      },

      login: async (email, password, organization) => {
        // Sign-in can replace another browser identity. Clear every
        // authorization-derived value before issuing the new request.
        const sessionEpoch = get().sessionEpoch + 1;
        usePermissionStore.getState().clearAuthorization();
        set({ isLoading: true, isHydrated: false, authorizationInitialized: false, sessionEpoch });
        try {
          const response = await authService.login(email, password, organization);
          const { access_token } = response.data;
          
          set({ token: access_token, refreshToken: null });
          setAccessToken(access_token);
          
          const meResponse = await authService.getMe(access_token);
          // An earlier refresh/hydration request must never overwrite a
          // successful interactive login.
          if (get().sessionEpoch !== sessionEpoch) return false;
          
          set({
            user: meResponse.data,
            isAuthenticated: true,
            isHydrated: true,
          });
          await get().initializeAuthorization();
          if (get().sessionEpoch !== sessionEpoch) return false;
          set({ isLoading: false });
          return true;
        } catch (error) {
          if (get().sessionEpoch !== sessionEpoch) throw error;
          setAccessToken(null);
          usePermissionStore.getState().clearAuthorization();
          set({ isLoading: false, token: null, refreshToken: null, isAuthenticated: false, user: null, isHydrated: true, authorizationInitialized: false });
          const detail = error?.response?.data?.detail;
          if (detail && error.response && error.response.data) {
            error.response.data.detail = detail;
          }
          throw error;
        }
      },

      logout: async () => {
        const sessionEpoch = get().sessionEpoch + 1;
        try {
          const { token } = get();
          if (token) {
            await authService.logout(token);
          }
        } catch (e) {
          // Ignore logout errors
          void e;
        } finally {
          setAccessToken(null);
          usePermissionStore.getState().clearAuthorization();
          set({
            user: null,
            token: null,
            refreshToken: null,
            isAuthenticated: false,
            isLoading: false,
            isHydrated: true,
            authorizationInitialized: false,
            sessionEpoch,
          });
        }
      },

      setToken: (token) => {
        setAccessToken(token);
        set({ token });
      },
      setRefreshToken: (refreshToken) => set({ refreshToken }),

      refreshAccessToken: async () => {
        const response = await authService.refreshToken();
        setAccessToken(response.data.access_token);
        set({ token: response.data.access_token, isAuthenticated: true });
        return response.data.access_token;
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
        if (state.isLoading) return;
        const sessionEpoch = state.sessionEpoch + 1;
        set({ isLoading: true, authorizationInitialized: false, sessionEpoch });
        if (state.token && !state.user) {
          authService
            .getMe(state.token)
            .then((res) => {
              if (get().sessionEpoch !== sessionEpoch) return null;
              set({ user: res.data, isAuthenticated: true, isHydrated: true });
              return get().initializeAuthorization();
            })
            .catch(() => {
              if (get().sessionEpoch !== sessionEpoch) return;
              usePermissionStore.getState().clearAuthorization();
              set({
                user: null,
                token: null,
                refreshToken: null,
                isAuthenticated: false,
                isHydrated: true,
              });
            })
            .finally(() => {
              if (get().sessionEpoch === sessionEpoch) set({ isLoading: false });
            });
        } else {
          // The access token deliberately is not persisted. Restore a browser
          // session through the HttpOnly refresh cookie after a reload.
          authService.refreshToken()
            .then((response) => {
              if (get().sessionEpoch !== sessionEpoch) return null;
              const token = response.data.access_token;
              setAccessToken(token);
              set({ token, isAuthenticated: true });
              return token;
            })
            .then((token) => authService.getMe(token))
            .then((res) => {
              if (get().sessionEpoch !== sessionEpoch) return null;
              set({ user: res.data, isAuthenticated: true, isHydrated: true });
              return get().initializeAuthorization();
            })
            .catch(() => {
              if (get().sessionEpoch !== sessionEpoch) return;
              usePermissionStore.getState().clearAuthorization();
              set({ user: null, token: null, refreshToken: null, isAuthenticated: false, isHydrated: true });
            })
            .finally(() => {
              if (get().sessionEpoch === sessionEpoch) set({ isLoading: false });
            });
        }
      },
    })
);
