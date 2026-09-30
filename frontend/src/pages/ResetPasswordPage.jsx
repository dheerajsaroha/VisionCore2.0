import React, { useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ShieldCheck, Lock, ArrowRight, AlertCircle, CheckCircle2, Circle } from 'lucide-react';
import { authService } from '../services/authService';
import { checkPassword } from '../utils/passwordPolicy';
import { Button, Card, CardContent } from '../components/ui';

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  // Arriving without a link token is the normal case for someone who read the
  // email on a phone and is now typing the 6-digit code. So this page offers
  // the code rather than only an error.
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const usingLink = Boolean(token);
  const [mode, setMode] = useState(usingLink ? 'link' : 'code');
  const activeMode = usingLink ? 'link' : mode;
  const canSubmitCode = /^\d{6}$/.test(code) && /\S+@\S+\.\S+/.test(email);

  // /auth/reset-password allows only 3 attempts per 5 minutes, so catching
  // an unmet rule here saves the user from being locked out by 422s.
  const checks = useMemo(() => checkPassword(password), [password]);
  const unmet = checks.filter((c) => !c.ok);

  const submit = async (event) => {
    event.preventDefault();
    if (password !== confirmPassword) {
      setMessage('Passwords do not match.');
      return;
    }
    if (unmet.length) {
      setMessage(
        `Password still needs: ${unmet.map((u) => u.label.toLowerCase()).join(', ')}.`
      );
      return;
    }
    if (activeMode === 'code' && !canSubmitCode) {
      setMessage('Enter your email address and the 6-digit code from the email.');
      return;
    }
    setLoading(true);
    setMessage('');
    try {
      await authService.resetPassword(
        activeMode === 'link'
          ? { token, newPassword: password }
          : { email: email.trim(), code: code.trim(), newPassword: password }
      );
      navigate('/login', { state: { reset: true } });
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Unable to reset password. Link may be expired.');
    } finally {
      setLoading(false);
    }
  };

  if (!token && mode !== 'code') {
    return (
      <div className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center px-4 font-sans">
        <Card className="w-full max-w-md bg-gray-900 border-gray-800 text-center p-8">
          <AlertCircle className="h-10 w-10 text-amber-400 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-white mb-2">Invalid Password Reset Link</h1>
          <p className="text-xs text-gray-400 mb-6">This password reset link is invalid or missing a security token.</p>
          <Link to="/forgot-password">
            <Button variant="primary" className="w-full py-2.5 rounded-xl font-bold">
              Request New Reset Link
            </Button>
          </Link>
          <button
            type="button"
            onClick={() => setMode('code')}
            className="mt-4 text-xs text-gray-400 hover:text-indigo-300 font-medium"
          >
            I have a 6-digit code instead
          </button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center px-4 py-12 font-sans relative overflow-hidden">
      {/* Background Ambient Light */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[400px] bg-indigo-600/15 rounded-full blur-[130px] pointer-events-none" />

      <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <Link to="/" className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-600/30">
              <ShieldCheck className="h-6 w-6 text-white" />
            </div>
            <span className="text-2xl font-extrabold tracking-tight text-white">
              VisionCore
            </span>
          </Link>
        </div>

        <Card className="bg-gray-900/90 border-gray-800 shadow-2xl backdrop-blur-xl">
          <CardContent className="p-8">
            <div className="text-center mb-6">
              <h1 className="text-2xl font-extrabold text-white mb-2">
                Choose a New Password
              </h1>
              <p className="text-xs text-gray-400">
                {activeMode === 'code'
                  ? 'Enter the code from your reset email, then choose a new password.'
                  : 'Your password needs all of the following.'}
              </p>
            </div>

            {password && (
              <ul className="mb-5 grid grid-cols-1 sm:grid-cols-2 gap-1.5" aria-live="polite">
                {checks.map((c) => (
                  <li
                    key={c.id}
                    className={`flex items-center gap-2 text-xs ${
                      c.ok ? 'text-emerald-400' : 'text-gray-500'
                    }`}
                  >
                    {c.ok ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <Circle className="h-3.5 w-3.5 shrink-0" />
                    )}
                    {c.label}
                  </li>
                ))}
              </ul>
            )}

            {message && (
              <div className="mb-6 rounded-xl bg-red-500/10 border border-red-500/20 p-4 text-xs text-red-400 font-medium flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{message}</span>
              </div>
            )}

            <form onSubmit={submit} className="space-y-4">
              {activeMode === 'code' && (
                <>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                      Email Address
                    </label>
                    <input
                      required
                      type="email"
                      autoComplete="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@company.com"
                      className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                      6-Digit Code
                    </label>
                    <input
                      required
                      type="text"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={6}
                      value={code}
                      onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                      placeholder="000000"
                      className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-center text-2xl tracking-[0.5em] text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500"
                    />
                    <p className="mt-2 text-[11px] text-gray-500">
                      {code.length}/6 digits.
                    </p>
                  </div>
                </>
              )}

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                  New Password
                </label>
                <div className="relative">
                  <input
                    required
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="New password"
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 pl-10 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                  />
                  <Lock className="absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                  Confirm New Password
                </label>
                <div className="relative">
                  <input
                    required
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter password"
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 pl-10 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                  />
                  <Lock className="absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
                </div>
              </div>

              <Button
                type="submit"
                disabled={
                  loading ||
                  unmet.length > 0 ||
                  password !== confirmPassword ||
                  (activeMode === 'code' && !canSubmitCode)
                }
                variant="primary"
                className="w-full py-3.5 rounded-xl font-bold shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 mt-4"
              >
                {loading ? 'Resetting Password...' : (
                  <>
                    <span>Reset Password & Sign In</span>
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>

              <div className="pt-2 text-center">
                {activeMode === 'link' ? (
                  <button
                    type="button"
                    onClick={() => setMode('code')}
                    className="text-xs text-gray-400 hover:text-indigo-300 font-medium"
                  >
                    I have a 6-digit code instead
                  </button>
                ) : (
                  token && (
                    <button
                      type="button"
                      onClick={() => setMode('link')}
                      className="text-xs text-gray-400 hover:text-indigo-300 font-medium"
                    >
                      Use my reset link instead
                    </button>
                  )
                )}
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
