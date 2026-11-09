import React, { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ShieldCheck, Sun, Moon, Monitor, Sparkles, Snowflake } from "lucide-react";
import { useTheme, AVAILABLE_THEMES } from "../../hooks/useTheme";
import { useAuthStore } from "../../store/authStore";

const THEME_ICONS = { dark: Moon, light: Sun, midnight: Sparkles, nordic: Snowflake };

/**
 * Public footer.
 *
 * Product destinations are in-page anchors rather than /dashboard routes:
 * those routes are auth-gated, so linking a logged-out visitor to them just
 * bounces them to the login screen. Legal-policy routes do not exist, so they
 * are not advertised here.
 */
export const Footer = () => {
  const { theme, setTheme } = useTheme();
  const location = useLocation();
  const [themeMenuOpen, setThemeMenuOpen] = useState(false);
  const isAuthenticated = useAuthStore((state) => Boolean(state.user));

  // eslint-disable-next-line react-hooks/set-state-in-effect -- Close the transient menu after navigation.
  useEffect(() => setThemeMenuOpen(false), [location.pathname, location.hash]);

  const jumpToSection = useCallback(
    (id) => (event) => {
      const target = document.getElementById(id);
      if (!target) return; // Not on the landing page: let the link do a normal navigation.
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      window.history.replaceState(null, "", `/#${id}`);
    },
    []
  );

  const CurrentIcon = THEME_ICONS[theme] || Monitor;

  return (
    <footer className="py-16 border-t border-gray-800 bg-gray-950 text-gray-400 font-sans text-sm">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 pb-12 border-b border-gray-800">
          {/* Brand Col */}
          <div className="col-span-2 space-y-4">
            <Link to="/" className="flex items-center gap-2" aria-label="VisionCore Home">
              <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <span className="text-white font-bold text-xl tracking-tight">VisionCore</span>
            </Link>
            <p className="text-xs text-gray-400 max-w-sm leading-relaxed">
              AI-powered enterprise workforce platform combining neural biometrics, multi-tenant RBAC,
              automated payroll calculation, and interactive AI copilots.
            </p>
            <div className="flex items-center gap-3 pt-2">
              {/* Full theme list, matching the navbar switcher: a two-way toggle
                  would strand the midnight and nordic themes. */}
              <div className="relative">
                <button
                  onClick={() => setThemeMenuOpen((open) => !open)}
                  className="px-3 py-1.5 rounded-lg border border-gray-800 bg-gray-900 text-xs font-semibold text-gray-300 hover:text-white flex items-center gap-2 transition-colors"
                  aria-haspopup="true"
                  aria-expanded={themeMenuOpen}
                >
                  <CurrentIcon className="h-3.5 w-3.5 text-amber-400" />
                  <span>Theme</span>
                </button>
                {themeMenuOpen && (
                  <ul className="absolute left-0 bottom-full mb-2 w-44 bg-gray-900 border border-gray-800 rounded-xl shadow-2xl p-1.5 z-50">
                    {AVAILABLE_THEMES.map((option) => {
                      const Icon = THEME_ICONS[option.id] || Monitor;
                      const selected = option.id === theme;
                      return (
                        <li key={option.id}>
                          <button
                            onClick={() => {
                              setTheme(option.id);
                              setThemeMenuOpen(false);
                            }}
                            aria-pressed={selected}
                            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium text-left transition-colors ${
                              selected
                                ? "bg-indigo-600 text-white"
                                : "text-gray-300 hover:bg-gray-800 hover:text-white"
                            }`}
                          >
                            <Icon className="h-3.5 w-3.5 shrink-0" />
                            {option.label}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </div>
          </div>

          {/* Product Links — anchors into the landing page sections */}
          <div className="space-y-3">
            <p className="text-xs font-bold text-white uppercase tracking-wider">Product</p>
            <ul className="space-y-2 text-xs">
              <li>
                <a href="/#platform" onClick={jumpToSection("platform")} className="hover:text-white transition-colors">Platform Overview</a>
              </li>
              <li>
                <a href="/#features" onClick={jumpToSection("features")} className="hover:text-white transition-colors">Capability Suite</a>
              </li>
              <li>
                <a href="/#ai" onClick={jumpToSection("ai")} className="hover:text-white transition-colors">AI &amp; Copilots</a>
              </li>
              <li>
                <a href="/#security" onClick={jumpToSection("security")} className="hover:text-white transition-colors">Security &amp; Tenancy</a>
              </li>
              <li>
                <a href="/#pricing" onClick={jumpToSection("pricing")} className="hover:text-white transition-colors">Pricing</a>
              </li>
              <li>
                <a href="/#preview" onClick={jumpToSection("preview")} className="hover:text-white transition-colors">Product Preview</a>
              </li>
            </ul>
          </div>

          {/* Capabilities */}
          <div className="space-y-3">
            <p className="text-xs font-bold text-white uppercase tracking-wider">Capabilities</p>
            <ul className="space-y-2 text-xs">
              <li>
                <Link to="/dashboard/attendance" className="hover:text-white transition-colors">Biometric Attendance</Link>
              </li>
              <li>
                <Link to="/dashboard/hr" className="hover:text-white transition-colors">HCM &amp; Org Tree</Link>
              </li>
              <li>
                <Link to="/dashboard/performance" className="hover:text-white transition-colors">Performance &amp; OKRs</Link>
              </li>
              <li>
                <Link to="/dashboard/payroll" className="hover:text-white transition-colors">Payroll &amp; Taxes</Link>
              </li>
            </ul>
          </div>

          {/* Auth & Account */}
          <div className="space-y-3">
            <p className="text-xs font-bold text-white uppercase tracking-wider">Access</p>
            <ul className="space-y-2 text-xs">
              {isAuthenticated ? (
                <li>
                  <Link to="/dashboard" className="hover:text-white transition-colors">Dashboard Overview</Link>
                </li>
              ) : (
                <>
                  <li>
                    <Link to="/login" className="hover:text-white transition-colors">Sign In</Link>
                  </li>
                  <li>
                    <Link to="/signup" className="hover:text-white transition-colors">Register Account</Link>
                  </li>
                  <li>
                    <Link to="/forgot-password" className="hover:text-white transition-colors">Reset Password</Link>
                  </li>
                </>
              )}
              <li>
                <a href="/#get-started" onClick={jumpToSection("get-started")} className="hover:text-white transition-colors">Get Started</a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 flex flex-col sm:flex-row justify-between items-center gap-4 text-xs text-gray-500">
          <p>© 2026 VisionCore Enterprise Workforce Platform. All rights reserved.</p>
          <p className="flex items-center gap-2">
            <ShieldCheck className="h-3.5 w-3.5 text-indigo-400" />
            27 scoped RBAC roles across platform, organization and system tiers
          </p>
        </div>
      </div>
    </footer>
  );
};
