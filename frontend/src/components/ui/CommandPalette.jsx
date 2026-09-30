import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  LayoutDashboard,
  Clock,
  Users,
  BarChart3,
  Settings,
  Ticket,
  CreditCard,
  Receipt,
  Shield,
  ShieldCheck,
  Calendar,
  Trophy,
  Briefcase,
  BookOpen,
  TrendingUp,
  BrainCircuit,
  Database,
  Bot,
  Sparkles,
  ArrowRight,
  Command,
  X,
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { usePermission } from '../../hooks/usePermission';
import { canAccess, resolvePolicy } from '../../lib/accessControl';

const COMMAND_ITEMS = [
  { label: 'Dashboard Overview', path: '/dashboard', icon: LayoutDashboard, group: 'Core' },
  { label: 'Organization & Business Units', path: '/dashboard/organization', icon: Users, group: 'Core' },
  { label: 'Identity Directory & Workforce', path: '/dashboard/identity-directory', icon: Users, group: 'Core', keywords: 'users employees people staff management directory' },
  { label: 'Biometric Attendance Check-in', path: '/dashboard/attendance', icon: Clock, group: 'Workforce' },
  { label: 'Leave Management', path: '/dashboard/leave', icon: Calendar, group: 'Workforce' },
  { label: 'Workforce Attendance Dashboard', path: '/dashboard/workforce/attendance', icon: Clock, group: 'Workforce' },
  { label: 'Shift Calendar Planner', path: '/dashboard/workforce/shifts', icon: Calendar, group: 'Workforce' },
  { label: 'Roster Planner', path: '/dashboard/workforce/rosters', icon: Calendar, group: 'Workforce' },
  { label: 'Attendance Analytics & Reports', path: '/dashboard/workforce/analytics', icon: BarChart3, group: 'Analytics' },
  { label: 'HR Center & HCM Directory', path: '/dashboard/hr', icon: Users, group: 'HCM' },
  { label: 'Performance Management & OKRs', path: '/dashboard/performance', icon: Trophy, group: 'HCM' },
  { label: 'Learning & Development Courses', path: '/dashboard/learning', icon: BookOpen, group: 'HCM' },
  { label: 'Recruitment & Open Positions', path: '/dashboard/open-positions', icon: Briefcase, group: 'HCM' },
  { label: 'Automated Payroll & Payslips', path: '/dashboard/payroll', icon: CreditCard, group: 'Operations' },
  { label: 'Reimbursement Claims', path: '/dashboard/reimbursements', icon: Receipt, group: 'Operations' },
  { label: 'Service Ticketing System', path: '/dashboard/ticketing', icon: Ticket, group: 'Operations' },
  { label: 'Asset Management', path: '/dashboard/assets', icon: Shield, group: 'Operations' },
  { label: 'AI Studio & Prompt Playground', path: '/dashboard/ai-studio', icon: BrainCircuit, group: 'AI Platform' },
  { label: 'AI RAG Knowledge Center', path: '/dashboard/knowledge-center', icon: Database, group: 'AI Platform' },
  { label: 'AI Copilot Hub', path: '/dashboard/ai-copilot-hub', icon: Bot, group: 'AI Platform' },
  { label: 'AI Analytics & Token Usage', path: '/dashboard/ai-analytics', icon: Sparkles, group: 'AI Platform' },
  { label: '27-Role Permission Matrix', path: '/dashboard/permissions', icon: ShieldCheck, group: 'Governance' },
  { label: 'Tenant Administration', path: '/dashboard/tenant-admin', icon: Settings, group: 'Admin' },
  { label: 'System & Account Settings', path: '/dashboard/settings', icon: Settings, group: 'Admin' },
];

export function CommandPalette({ isOpen, onClose }) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const { hasPermission, hasFeature } = usePermission();
  const navigate = useNavigate();
  const inputRef = useRef(null);

  // Only destinations the caller can actually open. The palette previously
  // offered all 24 targets to every user, so searching for "payroll" as an
  // employee produced a hit that then denied access.
  const accessibleItems = COMMAND_ITEMS.filter((item) =>
    canAccess(resolvePolicy(item.path), {
      hasPermission,
      hasFeature,
      isAuthenticated: true,
    }).allowed
  );

  const filteredItems = accessibleItems.filter((item) =>
    item.label.toLowerCase().includes(query.toLowerCase()) ||
    item.group.toLowerCase().includes(query.toLowerCase()) ||
    (item.keywords && item.keywords.toLowerCase().includes(query.toLowerCase()))
  );

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setSelectedIndex(0);
    } else {
      setQuery('');
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!isOpen) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredItems.length));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % Math.max(1, filteredItems.length));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filteredItems[selectedIndex]) {
          navigate(filteredItems[selectedIndex].path);
          onClose();
        }
      } else if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, filteredItems, selectedIndex, navigate, onClose]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[1500] flex items-start justify-center pt-20 px-4 bg-black/60 backdrop-blur-md">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: -10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -10 }}
          transition={{ duration: 0.15 }}
          className="w-full max-w-2xl rounded-2xl bg-gray-900 border border-gray-800 shadow-2xl overflow-hidden text-white font-sans"
        >
          {/* Header Input */}
          <div className="flex items-center px-4 border-b border-gray-800 bg-gray-950/80">
            <Search className="h-5 w-5 text-gray-400 shrink-0 mr-3" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              placeholder="Type a command or search page (e.g. Attendance, AI, Payroll)..."
              className="w-full py-4 bg-transparent text-sm text-white placeholder-gray-500 focus:outline-none"
            />
            <button
              onClick={onClose}
              className="p-1 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Results List */}
          <div className="max-h-96 overflow-y-auto p-2 divide-y divide-gray-800/40 hide-scrollbar">
            {filteredItems.length === 0 ? (
              <div className="py-8 text-center text-xs text-gray-400">
                No matching page or command found for "{query}".
              </div>
            ) : (
              filteredItems.map((item, idx) => {
                const Icon = item.icon;
                const isSelected = idx === selectedIndex;
                return (
                  <div
                    key={item.path + item.label}
                    onClick={() => {
                      navigate(item.path);
                      onClose();
                    }}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex items-center justify-between px-3 py-3 rounded-xl cursor-pointer text-xs sm:text-sm font-medium transition-all ${
                      isSelected ? 'bg-indigo-600 text-white' : 'text-gray-300 hover:bg-gray-800/60'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${isSelected ? 'bg-indigo-500 text-white' : 'bg-gray-800 text-indigo-400'}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="font-semibold">{item.label}</div>
                        <div className={`text-[11px] ${isSelected ? 'text-indigo-200' : 'text-gray-500'}`}>{item.path}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        isSelected ? 'bg-indigo-500 text-white' : 'bg-gray-800 text-gray-400'
                      }`}>
                        {item.group}
                      </span>
                      <ArrowRight className={`h-4 w-4 ${isSelected ? 'opacity-100' : 'opacity-0'}`} />
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer Shortcuts Info */}
          <div className="px-4 py-2.5 border-t border-gray-800 bg-gray-950/80 flex items-center justify-between text-[11px] text-gray-400 font-mono">
            <div className="flex items-center gap-3">
              <span><kbd className="px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700">↑</kbd> <kbd className="px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700">↓</kbd> Navigate</span>
              <span><kbd className="px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700">↵</kbd> Select</span>
              <span><kbd className="px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700">ESC</kbd> Close</span>
            </div>
            <div className="flex items-center gap-1 font-sans font-semibold text-indigo-400">
              <Command className="h-3 w-3" /> VisionCore Quick Command
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
