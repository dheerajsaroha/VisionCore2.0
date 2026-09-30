import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Mail, ArrowLeft, CheckCircle2, AlertCircle } from 'lucide-react';
import { authService } from '../services/authService';
import { Button, Card, CardContent } from '../components/ui';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await authService.forgotPassword(email);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to request password reset.');
    } finally {
      setLoading(false);
    }
  };

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
                Reset your password
              </h1>
              <p className="text-xs text-gray-400 leading-relaxed">
                Enter your registered email address and we'll issue a password reset link.
              </p>
            </div>

            {error && (
              <div className="mb-6 rounded-xl bg-red-500/10 border border-red-500/20 p-4 text-xs text-red-400 font-medium flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {result ? (
              <div className="space-y-4 text-center">
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 font-medium">
                  <CheckCircle2 className="h-5 w-5 text-emerald-400 mx-auto mb-2" />
                  {result.detail}
                  {result.reset_url && (
                    <a
                      href={result.reset_url}
                      className="mt-3 inline-block px-4 py-2 rounded-lg bg-emerald-600 text-white font-bold text-xs hover:bg-emerald-500 transition-colors"
                    >
                      Open Development Reset Link
                    </a>
                  )}
                </div>
                <Link to="/login" className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-400 hover:text-indigo-300">
                  <ArrowLeft className="h-3.5 w-3.5" />
                  <span>Return to Sign In</span>
                </Link>
              </div>
            ) : (
              <form onSubmit={submit} className="space-y-5">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                    Email Address
                  </label>
                  <div className="relative">
                    <input
                      required
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@company.com"
                      className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 pl-10 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                    />
                    <Mail className="absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={loading}
                  variant="primary"
                  className="w-full py-3.5 rounded-xl font-bold shadow-lg shadow-indigo-600/30"
                >
                  {loading ? 'Sending Request...' : 'Send Password Reset Link'}
                </Button>

                <div className="text-center pt-4 border-t border-gray-800">
                  <Link to="/login" className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-400 hover:text-indigo-300">
                    <ArrowLeft className="h-3.5 w-3.5" />
                    <span>Back to Sign In</span>
                  </Link>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
