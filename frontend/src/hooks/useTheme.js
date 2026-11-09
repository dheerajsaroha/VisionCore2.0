/**
 * useTheme — Phase 2 Multi-Theme Engine & Branding Hook
 *
 * Supports 4 themes:
 *   - 'dark' (Default Dark Mode - Deep Slate & Indigo)
 *   - 'light' (Clean Light Mode - Crisp White & Slate)
 *   - 'midnight' (Midnight Cyberpunk - Obsidian & Neon Purple)
 *   - 'nordic' (Nordic Frost - Arctic Navy & Cool Teal)
 *
 * Usage:
 *   const { theme, setTheme, cycleTheme, availableThemes } = useTheme();
 */
import { useSyncExternalStore, useCallback } from 'react';

const STORAGE_KEY = 'visioncore_theme';
export const VALID_THEMES = ['dark', 'light', 'midnight', 'nordic'];
export const DEFAULT_THEME = 'dark';

export const AVAILABLE_THEMES = [
  { id: 'dark', label: 'Dark Slate', icon: 'Moon', color: '#6366f1' },
  { id: 'light', label: 'Light Clean', icon: 'Sun', color: '#4f46e5' },
  { id: 'midnight', label: 'Midnight Neon', icon: 'Sparkles', color: '#a855f7' },
  { id: 'nordic', label: 'Nordic Frost', icon: 'Snowflake', color: '#14b8a6' },
];

function applyTheme(theme) {
  const root = document.documentElement;
  VALID_THEMES.forEach((t) => root.classList.remove(t));
  root.classList.add(theme);
}

function getStoredTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem('visioncore-theme');
    if (stored && VALID_THEMES.includes(stored)) return stored;
  } catch {
    // localStorage fallback
  }
  return DEFAULT_THEME;
}

function storeTheme(theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
    localStorage.setItem('visioncore-theme', theme);
  } catch {
    // silent
  }
}

// Singleton theme listener state
let _listeners = [];
let _currentTheme = getStoredTheme();

// Apply immediately on script load
applyTheme(_currentTheme);

function notifyListeners(theme) {
  _listeners.forEach((fn) => fn(theme));
}

function subscribeToTheme(listener) {
  _listeners.push(listener);
  return () => {
    _listeners = _listeners.filter((fn) => fn !== listener);
  };
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribeToTheme, () => _currentTheme, () => DEFAULT_THEME);

  const setTheme = useCallback((newTheme) => {
    if (!VALID_THEMES.includes(newTheme)) return;
    _currentTheme = newTheme;
    applyTheme(newTheme);
    storeTheme(newTheme);
    notifyListeners(newTheme);
  }, []);

  const cycleTheme = useCallback(() => {
    const currentIndex = VALID_THEMES.indexOf(_currentTheme);
    const nextIndex = (currentIndex + 1) % VALID_THEMES.length;
    setTheme(VALID_THEMES[nextIndex]);
  }, [setTheme]);

  return {
    theme,
    setTheme,
    cycleTheme,
    availableThemes: AVAILABLE_THEMES,
  };
}
