/**
 * Attendance / Biometric Kiosk Page
 * Fixes: live clock (interval), consistent dark design, toast on success/fail.
 */
import React, { useState, useRef, useCallback, useEffect } from 'react';
import Webcam from 'react-webcam';
import { motion } from 'framer-motion';
import { Camera, CheckCircle2, XCircle, Clock, RefreshCw, Activity, Calendar, FileEdit } from 'lucide-react';
import { attendanceService } from '../services/attendanceService';
import { locationFields } from '../services/geolocation';
import { workforceService } from '../services/workforceService';
import { useAuthStore } from '../store/authStore';
import { usePermission } from '../hooks/usePermission';
import { useToast } from '../components/ui/Toast';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { formatTime, formatDate, titleCase } from '../lib/utils';
import { EmployeeDetailModal } from '../components/EmployeeDetailModal';
import { BiometricAvatar } from '../components/directory/BiometricAvatar';
import { Modal } from '../components/ui/Modal';


export default function Attendance() {
  const webcamRef  = useRef(null);
  const timeoutRef = useRef(null);
  const clockRef   = useRef(null);

  const [step,        setStep]        = useState('idle'); // idle | processing | success | fail
  const [logs,        setLogs]        = useState([]);
  const [cameraReady, setCameraReady] = useState(false);
  const [result,      setResult]      = useState(null);
  const [clock,       setClock]       = useState(new Date());
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [correctionLog, setCorrectionLog] = useState(null);
  const [correctionReason, setCorrectionReason] = useState('');
  const [requestedIn, setRequestedIn] = useState('');
  const [requestedOut, setRequestedOut] = useState('');
  const [correctionLoading, setCorrectionLoading] = useState(false);
  const [correctionError, setCorrectionError] = useState('');


  const { user }  = useAuthStore();
  const { hasPermission } = usePermission();
  const toast     = useToast();
  const canRequestCorrection = hasPermission('attendance_correction:create');

  /* Live clock — updates every second */
  useEffect(() => {
    clockRef.current = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(clockRef.current);
  }, []);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await attendanceService.getLogs({ limit: 12 });
      setLogs(res.data || []);
    } catch {
      /* silent */
    }
  }, []);

  useEffect(() => {
    fetchLogs();
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [fetchLogs]);

  const fetchCorrections = useCallback(async () => {
    if (!canRequestCorrection) return;
    try {
      await workforceService.corrections.listMine();
    } catch {
    }
  }, [canRequestCorrection]);

  useEffect(() => { fetchCorrections(); }, [fetchCorrections]);

  const openCorrection = (log) => {
    setCorrectionLog(log);
    setCorrectionError('');
    setCorrectionReason('');
    setRequestedIn(log.check_in ? new Date(log.check_in).toISOString().slice(0, 16) : '');
    setRequestedOut(log.check_out ? new Date(log.check_out).toISOString().slice(0, 16) : '');
  };

  const submitCorrection = async (event) => {
    event.preventDefault();
    if (!correctionLog || !correctionReason.trim()) return;
    setCorrectionLoading(true);
    setCorrectionError('');
    try {
      await workforceService.corrections.create({
        attendance_log_id: correctionLog.id,
        request_payload: {
          requested_clock_in: requestedIn ? new Date(requestedIn).toISOString() : undefined,
          requested_clock_out: requestedOut ? new Date(requestedOut).toISOString() : undefined,
          reason: correctionReason.trim(),
        },
      });
      toast({ message: 'Correction request submitted for review.', type: 'success' });
      setCorrectionLog(null);
      await fetchCorrections();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : detail?.message || 'Unable to submit correction request.';
      setCorrectionError(message);
    } finally {
      setCorrectionLoading(false);
    }
  };

  const reset = useCallback(() => {
    setStep('idle');
    setResult(null);
  }, []);

  const capture = useCallback(async () => {
    if (step !== 'idle') return;
    setStep('processing');

    const imageSrc = webcamRef.current?.getScreenshot();
    if (!imageSrc) {
      setStep('idle');
      toast({
        message: 'Unable to capture a camera frame. Check camera access and try again.',
        type: 'error',
      });
      return;
    }

    try {
      // Geo-tagging is optional: a null result (denied, unavailable, or no
      // provider) still clocks the user in, just without coordinates.
      const geo = await locationFields();

      const response = await attendanceService.checkIn({
        image_base64: imageSrc.split(',')[1],
        // Identity, liveness and check-in time are determined server-side by
        // the canonical biometric attendance pipeline.
        source:       'ai',
        ...geo,
      });
      const data = response.data;
      setResult({
        name:   user?.full_name || 'User',
        time:   new Date(data.check_in).toLocaleTimeString(),
        status: data.status,
      });
      setStep('success');
      toast({
        message: `✅ Welcome, ${user?.full_name || 'User'}! Logged as ${titleCase(data.status)}.`,
        type: 'success',
        duration: 4000,
      });
      await fetchLogs();
      timeoutRef.current = setTimeout(reset, 4000);
    } catch (err) {
      setStep('fail');
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string'
        ? detail
        : detail?.message || 'Face not recognized. Please try again.';
      toast({ message: msg, type: 'error' });
      timeoutRef.current = setTimeout(reset, 3000);
    }
  }, [step, user, reset, toast, fetchLogs]);

  const handleCheckOut = useCallback(async () => {
    try {
      const response = await attendanceService.checkOut();
      const data = response.data;
      toast({
        message: `👋 Check-out recorded for ${data.user_name || 'User'} at ${new Date(data.check_out).toLocaleTimeString()}`,
        type: 'info',
        duration: 4000,
      });
      await fetchLogs();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string'
        ? detail
        : detail?.message || 'Check-out failed. Ensure you have an active check-in.';
      toast({ message: msg, type: 'error' });
    }
  }, [toast, fetchLogs]);


  return (
    <>
      <motion.div
        className="space-y-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
    >
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Biometric Kiosk</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Secure, frictionless AI attendance tracking
          </p>
        </div>
        {/* Live clock badge */}
        <div className="flex items-center gap-2 bg-gray-800/70 border border-gray-700/50 rounded-xl px-4 py-2 self-start sm:self-auto">
          <Calendar className="h-4 w-4 text-gray-500" />
          <span className="text-sm text-gray-300 font-medium">
            {clock.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })}
          </span>
          <span className="h-3 w-px bg-gray-700 mx-1" />
          <Clock className="h-4 w-4 text-indigo-400" />
          <span className="font-mono text-sm font-semibold text-indigo-300 tracking-wide tabular-nums">
            {clock.toLocaleTimeString()}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* ── Webcam Section ───────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="lg:col-span-2"
        >
          <Card className="overflow-hidden border-gray-800/60 bg-gray-900 p-0 flex flex-col">
            {/* Camera viewport */}
            <div className="relative aspect-video w-full bg-black rounded-t-xl overflow-hidden">
              <Webcam
                audio={false}
                ref={webcamRef}
                screenshotFormat="image/jpeg"
                className="w-full h-full object-cover"
                videoConstraints={{ facingMode: 'user' }}
                onUserMedia={()      => setCameraReady(true)}
                onUserMediaError={() => setCameraReady(false)}
              />

              {/* Processing overlay */}
              {step === 'processing' && (
                <div className="absolute inset-0 bg-black/60 backdrop-blur-md flex flex-col items-center justify-center text-white z-10">
                  <Spinner size="xl" className="text-indigo-400" />
                  <p className="mt-4 text-sm font-medium animate-pulse">Running neural identification…</p>
                </div>
              )}

              {/* Success overlay */}
              {step === 'success' && (
                <motion.div
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  className="absolute inset-0 bg-emerald-600/85 backdrop-blur-md flex flex-col items-center justify-center text-white z-10"
                >
                  <CheckCircle2 className="h-20 w-20 mb-3 drop-shadow-xl" />
                  <p className="text-2xl font-bold tracking-tight">Identity Verified</p>
                  <p className="text-sm opacity-90 mt-1">{result?.name}</p>
                  <p className="text-xs opacity-70 mt-0.5">{result?.time}</p>
                  <Badge className="mt-3 bg-white/20 text-white border-0 py-1 px-4 text-sm">
                    {titleCase(result?.status)}
                  </Badge>
                </motion.div>
              )}

              {/* Fail overlay */}
              {step === 'fail' && (
                <motion.div
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  className="absolute inset-0 bg-red-700/85 backdrop-blur-md flex flex-col items-center justify-center text-white z-10"
                >
                  <XCircle className="h-20 w-20 mb-3 drop-shadow-xl" />
                  <p className="text-2xl font-bold tracking-tight">Access Denied</p>
                  <p className="text-sm opacity-80 mt-1">Could not match neural template.</p>
                  <Button variant="secondary" className="mt-5 font-semibold" onClick={reset}>
                    <RefreshCw className="mr-2 h-4 w-4" /> Try Again
                  </Button>
                </motion.div>
              )}

              {/* Idle face guide */}
              {step === 'idle' && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="w-44 h-60 border-2 border-white/20 border-dashed rounded-[3rem] shadow-[0_0_0_9999px_rgba(0,0,0,0.35)]" />
                  <div className="absolute bottom-5 bg-black/60 backdrop-blur-sm text-white px-4 py-1.5 rounded-full text-xs font-medium border border-white/10 flex items-center gap-2">
                    <Activity className="h-3 w-3 text-emerald-400" />
                    Align face within the frame
                  </div>
                </div>
              )}
            </div>

            {/* Capture controls */}
            <CardContent className="p-5 bg-gray-900 rounded-b-xl">
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                {/* Camera status */}
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium
                  ${cameraReady
                    ? 'border-emerald-800/50 bg-emerald-950/40 text-emerald-400'
                    : 'border-gray-700 bg-gray-800/40 text-gray-500'}`
                }>
                  <span className={`h-2 w-2 rounded-full ${cameraReady ? 'bg-emerald-400 animate-pulse' : 'bg-gray-600'}`} />
                  {cameraReady ? 'Camera ready' : 'Waiting for camera…'}
                </div>

                <div className="flex items-center gap-3 w-full sm:w-auto">
                  <Button
                    onClick={capture}
                    disabled={step !== 'idle' || !cameraReady}
                    className="flex-1 sm:flex-initial px-6 py-5 text-base font-semibold rounded-xl bg-indigo-600 hover:bg-indigo-500 shadow-xl shadow-indigo-500/20 active:scale-95 transition-all"
                  >
                    <Camera className="mr-2 h-5 w-5" />
                    Authenticate
                  </Button>
                  <Button
                    onClick={handleCheckOut}
                    variant="outline"
                    className="flex-1 sm:flex-initial px-6 py-5 text-base font-semibold rounded-xl border-gray-700 bg-gray-800/80 hover:bg-gray-700 text-gray-200 shadow-md active:scale-95 transition-all"
                  >
                    <Clock className="mr-2 h-5 w-5 text-amber-400" />
                    Clock Out
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* ── Live Feed Sidebar ─────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="h-full flex flex-col border-gray-800/60">
            <CardHeader className="border-b border-gray-800/60 pb-4">
              <CardTitle className="text-white text-base">Live Feed</CardTitle>
              <CardDescription className="text-gray-500 text-xs">Recent successful check-ins</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto p-0 hide-scrollbar">
              {logs.length === 0 ? (
                <div className="p-8 text-center text-gray-600">
                  <Clock className="h-7 w-7 mx-auto mb-2 opacity-25" />
                  <p className="text-sm">Awaiting activity…</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-800/60">
                  {logs.map((log) => (
                    <div
                      key={log.id}
                      className="px-4 py-3 flex items-center justify-between hover:bg-gray-800/30 transition-colors cursor-pointer group"
                      onClick={() => setSelectedUserId(log.user_id)}
                      title="Click to view employee details"
                    >
                      <div className="flex items-center gap-3">
                        <BiometricAvatar
                          userId={log.user_id}
                          name={log.user_name}
                          className="group-hover:ring-1 group-hover:ring-indigo-500/40 transition-all"
                        />
                        <div>
                          <p className="text-sm font-semibold text-white leading-tight group-hover:text-indigo-300 transition-colors">
                            {log.user_name || `Employee #${log.user_id}`}
                          </p>
                          <p className="text-[11px] text-gray-500 mt-0.5">{formatDate(log.check_in)}</p>
                        </div>
                      </div>
                      <div className="text-right shrink-0 ml-2 flex items-end gap-2">
                        {canRequestCorrection && log.user_id === user?.id && (
                          <Button
                            type="button"
                            variant="ghost"
                            className="px-2 py-1 text-[10px]"
                            onClick={(event) => { event.stopPropagation(); openCorrection(log); }}
                            title="Request attendance correction"
                          >
                            <FileEdit className="h-3 w-3" />
                          </Button>
                        )}
                        <div>
                        <Badge variant={log.status === 'on_time' ? 'success' : log.status === 'late' ? 'warning' : 'default'}
                          className="text-[10px] px-1.5 py-0.5">
                          {titleCase(log.status)}
                        </Badge>
                        <p className="text-[10px] font-mono text-gray-500 mt-0.5 block">{formatTime(log.check_in)}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </motion.div>

      <EmployeeDetailModal
        userId={selectedUserId}
        isOpen={!!selectedUserId}
        onClose={() => setSelectedUserId(null)}
      />
      <Modal isOpen={!!correctionLog} onClose={() => setCorrectionLog(null)} title="Request Attendance Correction">
        <form onSubmit={submitCorrection} className="space-y-4">
          {correctionError && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{correctionError}</div>}
          <p className="text-sm text-gray-400">
            Current: {correctionLog?.check_in ? new Date(correctionLog.check_in).toLocaleString() : 'No check-in'}
            {' → '}
            {correctionLog?.check_out ? new Date(correctionLog.check_out).toLocaleString() : 'No check-out'}
          </p>
          <Input label="Requested check-in" type="datetime-local" value={requestedIn} onChange={(event) => setRequestedIn(event.target.value)} />
          <Input label="Requested check-out" type="datetime-local" value={requestedOut} onChange={(event) => setRequestedOut(event.target.value)} />
          <Input label="Reason" value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} required placeholder="Explain the attendance correction" />
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={() => setCorrectionLog(null)}>Cancel</Button>
            <Button type="submit" isLoading={correctionLoading} disabled={!correctionReason.trim()}>Submit request</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
