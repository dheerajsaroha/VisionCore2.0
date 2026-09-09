/**
 * useTheme — Global theme management hook.
 *
 * Manages dark/light mode by toggling the 'dark' and 'light' classes on
 * document.documentElement. Uses localStorage for persistence.
 *
 * Usage:
 *   const { theme, setTheme } = useTheme();
 */
import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'visioncore_theme';
const VALID_THEMES = ['dark', 'light'];
const DEFAULT_THEME = 'dark';

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
    // localStorage unavailable (e.g. private browsing with strict settings)
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

// Singleton state so all useTheme() consumers share one value
let _listeners = [];
let _currentTheme = getStoredTheme();

// Apply immediately on module load so there's no flash of wrong theme
applyTheme(_currentTheme);

function notifyListeners(theme) {
  _listeners.forEach((fn) => fn(theme));
}

export function useTheme() {
  const [theme, setThemeState] = useState(_currentTheme);

  useEffect(() => {
    _listeners.push(setThemeState);
    // Sync in case another tab changed it
    setThemeState(_currentTheme);
    return () => {
      _listeners = _listeners.filter((fn) => fn !== setThemeState);
    };
  }, []);

  const setTheme = useCallback((newTheme) => {
    if (!VALID_THEMES.includes(newTheme)) return;
    _currentTheme = newTheme;
    applyTheme(newTheme);
    storeTheme(newTheme);
    notifyListeners(newTheme);
  }, []);

  return { theme, setTheme };
}
