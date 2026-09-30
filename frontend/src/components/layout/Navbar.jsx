import React, { useState, useRef, useEffect, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ShieldCheck, Menu, X, ChevronDown, Building2, BrainCircuit, Lock,
  LayoutGrid, Sparkles, Sun, Moon, Monitor, Snowflake, LogIn, ArrowRight,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useTheme, AVAILABLE_THEMES } from "../../hooks/useTheme";
import { useAuthStore } from "../../store/authStore";

/**
 * Public marketing navigation.
 *
 * Every entry points at an on-page anchor of the landing page, so navigation
 * never dumps a visitor into an authenticated route that would bounce them back
 * to the login screen. Module-level destinations live in the dashboard navbar.
 */
const SECTIONS = [
  { id: "platform", label: "Platform" },
  { id: "features", label: "Capabilities" },
  { id: "ai", label: "AI & Copilots" },
  { id: "security", label: "Security" },
  { id: "pricing", label: "Pricing" },
];

const SECTION_DETAIL = {
  platform: "Architecture, data flow and how a check-in is processed",
  features: "HCM, attendance, leave, performance, payroll and operations modules",
  ai: "Knowledge-grounded copilots, RAG search and model governance",
  security: "Role-based access control, audit trails and tenant isolation",
  pricing: "Plan tiers, seat limits and trial terms",
};

const THEME_ICONS = {
  dark: Moon,
  light: Sun,
  midnight: Sparkles,
  nordic: Snowflake,
};

/**
 * Theme switcher. Hoisted to module scope: defining it inside Navbar would
 * remount the menu on every render and trips the rules-of-hooks lint.
 */
const ThemeButton = ({
  className = "",
  theme,
  setTheme,
}) => {
  // Each instance owns its ref AND its open state.
  //
  // Both a desktop and a mobile ThemeButton are mounted at once, so sharing
  // either the ref or the open state across them broke theme switching: every
  // open instance registered a document mousedown listener, and the *other*
  // (hidden) instance's listener saw the click on the visible menu as an
  // outside click, unmounting the menu on mousedown. The click that calls
  // setTheme then never fired, so no theme was ever applied.
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);
  const CurrentIcon = THEME_ICONS[theme] || Monitor;

  useEffect(() => {
    if (!open) return undefined;
    const handlePointerDown = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div className={`relative ${className}`} ref={containerRef}>
      <button
        onClick={() => setOpen((value) => !value)}
        className="p-2.5 rounded-xl border border-gray-800 bg-gray-900/80 hover:bg-gray-800 text-gray-300 transition-all duration-200 flex items-center justify-center"
        title="Change theme"
        aria-label="Change theme"
        aria-haspopup="true"
        aria-expanded={open}
      >
        <CurrentIcon className="h-4 w-4 text-amber-400" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-2 w-48 bg-gray-900 border border-gray-800 rounded-xl shadow-2xl p-1.5 z-50"
            role="menu"
          >
            {AVAILABLE_THEMES.map((option) => {
              const Icon = THEME_ICONS[option.id] || Monitor;
              const selected = option.id === theme;
              return (
                <button
                  key={option.id}
                  onClick={() => {
                    setTheme(option.id);
                    setOpen(false);
                  }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-left transition-colors ${
                    selected
                      ? "bg-indigo-600 text-white"
                      : "text-gray-300 hover:bg-gray-800 hover:text-white"
                  }`}
                  role="menuitemradio"
                  aria-checked={selected}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="flex-1">{option.label}</span>
                  {selected && <span className="text-[10px] uppercase tracking-wide">Active</span>}
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export const Navbar = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [openDropdown, setOpenDropdown] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [activeSection, setActiveSection] = useState("");
  const dropdownRef = useRef(null);
  const closeTimerRef = useRef(null);
  const location = useLocation();

  const { theme, setTheme } = useTheme();
  const isAuthenticated = useAuthStore((state) => Boolean(state.user));
  const onLanding = location.pathname === "/";

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Close the menus on navigation and when focus leaves the navbar.
  useEffect(() => {
    setMobileOpen(false);
    setOpenDropdown(false);
  }, [location.pathname, location.hash]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpenDropdown(false);
      }
    };
    const handleEscape = (e) => {
      if (e.key === "Escape") {
        setOpenDropdown(false);
        setMobileOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  useEffect(() => () => clearTimeout(closeTimerRef.current), []);

  // Highlight the section currently in view.
  useEffect(() => {
    if (!onLanding) return undefined;
    const sections = SECTIONS.map(({ id }) => document.getElementById(id)).filter(Boolean);
    if (!sections.length) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) setActiveSection(visible.target.id);
      },
      { rootMargin: "-25% 0px -55% 0px", threshold: [0, 0.25, 0.5] }
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [onLanding]);

  // The dropdown stays open while the pointer is inside it, so the panel and
  // its trigger must share one container and the close must be debounced.
  const openMenu = () => {
    clearTimeout(closeTimerRef.current);
    setOpenDropdown(true);
  };

  const scheduleClose = () => {
    clearTimeout(closeTimerRef.current);
    closeTimerRef.current = setTimeout(() => setOpenDropdown(false), 180);
  };

  const scrollToSection = useCallback(
    (id) => (event) => {
      event.preventDefault();
      setOpenDropdown(false);
      setMobileOpen(false);
      const target = document.getElementById(id);
      if (!target) return;
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      window.history.replaceState(null, "", `/#${id}`);
    },
    []
  );

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "backdrop-blur-xl bg-gray-950/90 border-b border-white/10 shadow-lg"
          : "backdrop-blur-xl bg-gray-950/70 border-b border-white/5"
      }`}
      aria-label="Primary"
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex justify-between items-center">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2" aria-label="VisionCore Home">
          <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <ShieldCheck className="h-5 w-5 text-white" />
          </div>
          <span className="text-white font-bold text-xl tracking-tight">VisionCore</span>
        </Link>

        {/* Desktop Nav */}
        <div className="hidden lg:flex items-center gap-1">
          {onLanding ? (
            <>
              <a
                href="/#platform"
                onClick={scrollToSection("platform")}
                className={`px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                  activeSection === "platform"
                    ? "text-white bg-gray-800/60"
                    : "text-gray-300 hover:text-white hover:bg-gray-800/50"
                }`}
              >
                Platform
              </a>

              {/* One shared container keeps the panel open while hovered. */}
              <div
                ref={dropdownRef}
                className="relative"
                onMouseEnter={openMenu}
                onMouseLeave={scheduleClose}
              >
                <button
                  onClick={() => setOpenDropdown((open) => !open)}
                  className={`flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                    ["features", "ai", "security"].includes(activeSection)
                      ? "text-white bg-gray-800/60"
                      : "text-gray-300 hover:text-white hover:bg-gray-800/50"
                  }`}
                  aria-expanded={openDropdown}
                  aria-haspopup="true"
                >
                  <LayoutGrid className="h-4 w-4" />
                  Explore
                  <ChevronDown
                    className={`h-3.5 w-3.5 transition-transform ${openDropdown ? "rotate-180" : ""}`}
                  />
                </button>

                <AnimatePresence>
                  {openDropdown && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.15 }}
                      className="absolute left-0 top-full pt-2 w-80"
                      style={{ pointerEvents: openDropdown ? "auto" : "none" }}
                    >
                      <div
                        className="bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl py-2"
                        role="menu"
                      >
                        {[
                          { id: "features", label: "Capabilities", icon: LayoutGrid },
                          { id: "ai", label: "AI & Copilots", icon: BrainCircuit },
                          { id: "security", label: "Security & Tenancy", icon: Lock },
                        ].map((item) => (
                          <a
                            key={item.id}
                            href={`/#${item.id}`}
                            onClick={scrollToSection(item.id)}
                            className="flex items-start gap-3 px-4 py-3 hover:bg-gray-800/50 transition-colors"
                            role="menuitem"
                          >
                            <item.icon className="h-4 w-4 mt-0.5 text-indigo-400 shrink-0" />
                            <span className="flex flex-col gap-0.5">
                              <span className="text-sm font-medium text-white">{item.label}</span>
                              <span className="text-xs text-gray-500">{SECTION_DETAIL[item.id]}</span>
                            </span>
                          </a>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              <a
                href="/#pricing"
                onClick={scrollToSection("pricing")}
                className={`px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                  activeSection === "pricing"
                    ? "text-white bg-gray-800/60"
                    : "text-gray-300 hover:text-white hover:bg-gray-800/50"
                }`}
              >
                Pricing
              </a>

              <a
                href="/#get-started"
                onClick={scrollToSection("get-started")}
                className="px-4 py-2.5 rounded-xl text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-800/50 transition-all duration-200"
              >
                Contact
              </a>
            </>
          ) : (
            <Link
              to="/"
              className="px-4 py-2.5 rounded-xl text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-800/50 transition-all duration-200"
            >
              Back to site
            </Link>
          )}
        </div>

        {/* Desktop Actions */}
        <div className="hidden md:flex items-center gap-3">
          <ThemeButton
            theme={theme}
            setTheme={setTheme}
          />
          {isAuthenticated ? (
            <Link
              to="/dashboard"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold transition-all duration-200"
            >
              <Building2 className="h-4 w-4" />
              Dashboard
            </Link>
          ) : (
            <>
              <Link
                to="/login"
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800/50 transition-all duration-200"
              >
                <LogIn className="h-4 w-4" />
                Sign In
              </Link>
              <Link
                to="/signup"
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold transition-all duration-200 hover:shadow-[0_0_15px_rgba(99,102,241,0.5)]"
              >
                Get Started
                <ArrowRight className="h-4 w-4" />
              </Link>
            </>
          )}
        </div>

        {/* Mobile Toggle */}
        <div className="flex items-center gap-2 lg:hidden">
          <ThemeButton
            className="md:hidden"
            theme={theme}
            setTheme={setTheme}
          />
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="p-2 text-gray-400 hover:text-white transition-colors"
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileOpen}
            aria-controls="mobile-navigation"
          >
            {mobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            id="mobile-navigation"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="lg:hidden border-t border-white/5 bg-gray-950/95 overflow-hidden"
          >
            <div className="px-6 py-4 space-y-1 max-h-[70vh] overflow-y-auto">
              {onLanding
                ? SECTIONS.map((section) => (
                    <a
                      key={section.id}
                      href={`/#${section.id}`}
                      onClick={scrollToSection(section.id)}
                      className={`block px-3 py-2.5 text-sm font-medium rounded-xl transition-colors ${
                        activeSection === section.id
                          ? "text-white bg-gray-800/60"
                          : "text-gray-400 hover:text-white hover:bg-gray-800/50"
                      }`}
                    >
                      {section.label}
                    </a>
                  ))
                : null}
              {onLanding && (
                <a
                  href="/#get-started"
                  onClick={scrollToSection("get-started")}
                  className="block px-3 py-2.5 text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800/50 rounded-xl transition-colors"
                >
                  Contact
                </a>
              )}

              <div className="pt-4 mt-2 border-t border-white/10 flex flex-col gap-3">
                {isAuthenticated ? (
                  <Link
                    to="/dashboard"
                    onClick={() => setMobileOpen(false)}
                    className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-semibold"
                  >
                    <Building2 className="h-4 w-4" />
                    Dashboard
                  </Link>
                ) : (
                  <>
                    <Link
                      to="/login"
                      onClick={() => setMobileOpen(false)}
                      className="text-sm font-medium text-gray-400 hover:text-white transition-colors text-center"
                    >
                      Sign In
                    </Link>
                    <Link
                      to="/signup"
                      onClick={() => setMobileOpen(false)}
                      className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-semibold"
                    >
                      Get Started
                    </Link>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
};
