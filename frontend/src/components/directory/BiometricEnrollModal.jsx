/**
 * BiometricEnrollModal.jsx
 * Enterprise Biometric Facial Enrollment Dialog.
 * Uses live camera stream or photo capture with posture guide and neural embedding registration.
 */
import React, { useRef, useState } from 'react';
import Webcam from 'react-webcam';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Fingerprint, Camera, Shield, AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react';
import userService from '../../services/userService';

export function BiometricEnrollModal({
  isOpen,
  onClose,
  user,
  onSuccess,
}) {
  const webcamRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [capturedImage, setCapturedImage] = useState(null);

  if (!isOpen || !user) return null;

  const dataURLtoFile = (dataurl, filename) => {
    const arr = dataurl.split(',');
    const mime = arr[0].match(/:(.*?);/)[1];
    const bstr = atob(arr[1]);
    let n = bstr.length;
    const u8arr = new Uint8Array(n);
    while (n--) {
      u8arr[n] = bstr.charCodeAt(n);
    }
    return new File([u8arr], filename, { type: mime });
  };

  const handleCapture = () => {
    if (!webcamRef.current) return;
    const screenshot = webcamRef.current.getScreenshot();
    if (!screenshot) {
      setError('Unable to capture camera stream. Ensure camera access is allowed.');
      return;
    }
    setCapturedImage(screenshot);
    setError('');
  };

  const handleRetake = () => {
    setCapturedImage(null);
    setError('');
  };

  const handleSubmit = async () => {
    if (!capturedImage) return;
    setLoading(true);
    setError('');
    try {
      const file = dataURLtoFile(capturedImage, `face_${user.id}_${Date.now()}.jpg`);
      await userService.enrollFace(user.id, file);
      // The stored capture changed; drop the cached avatar so the new photo shows.
      userService.clearFacePhotoCache(user.id);
      if (onSuccess) onSuccess();
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Biometric enrollment failed. Ensure face is clearly visible.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Biometric Face Enrollment: ${user.full_name}`}
      description="Register or update high-assurance neural biometric embedding for kiosk attendance."
      size="md"
    >
      <div className="space-y-4 pt-2 text-xs">
        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Camera Viewport / Frame */}
        <div className="relative aspect-video bg-black/90 rounded-2xl overflow-hidden shadow-inner border border-gray-800 flex items-center justify-center">
          {capturedImage ? (
            <img
              src={capturedImage}
              alt="Captured identity face"
              className="w-full h-full object-cover"
            />
          ) : (
            <>
              <Webcam
                audio={false}
                ref={webcamRef}
                screenshotFormat="image/jpeg"
                videoConstraints={{ facingMode: 'user', width: 1280, height: 720 }}
                className="w-full h-full object-cover"
              />
              {/* Face Guide Overlay */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-48 h-60 sm:w-56 sm:h-72 border-2 border-emerald-400/60 border-dashed rounded-full shadow-[0_0_0_9999px_rgba(0,0,0,0.45)]" />
              </div>
            </>
          )}

          {/* Status Overlay Badge */}
          <div className="absolute top-3 left-3 bg-gray-950/80 backdrop-blur-md px-2.5 py-1 rounded-lg border border-gray-800 text-[10px] text-gray-300 flex items-center gap-1.5">
            <Shield className="h-3 w-3 text-cyan-400" />
            <span>{capturedImage ? 'Frame Frozen' : 'Live Camera Feed'}</span>
          </div>
        </div>

        {/* Guidance Tip */}
        <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 text-[11px] space-y-1.5">
          <p className="flex items-center gap-2">
            <Fingerprint className="h-4 w-4 shrink-0 text-cyan-400" />
            <span>
              Center the employee&apos;s face directly within the oval guide in a well-lit environment without obstructions.
            </span>
          </p>
          <ul className="pl-6 list-disc space-y-0.5 text-cyan-200/80">
            <li>JPEG or PNG photo, at least 1 KB and under 10 MB.</li>
            <li>
              Exactly one face must be detected — no second person, no reflections or
              pictures of faces in the background.
            </li>
            <li>
              Face should fill roughly a fifth of the frame width (about 200px+ at 1280x720) and be
              frontal, sharp and evenly lit.
            </li>
            <li>
              A stored photo of a face is rejected by liveness as a spoof, so this must be a live
              camera capture of the employee.
            </li>
          </ul>
        </div>

        {/* Action Controls */}
        <div className="flex items-center justify-between pt-3 border-t border-gray-800/80">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={loading}
            className="text-xs text-gray-400 hover:text-gray-100"
          >
            Cancel
          </Button>

          <div className="flex items-center gap-2">
            {capturedImage ? (
              <>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleRetake}
                  disabled={loading}
                  className="text-xs border-gray-700 text-gray-300 hover:bg-gray-800"
                >
                  <RefreshCw className="h-3.5 w-3.5 mr-1" />
                  Retake Photo
                </Button>
                <Button
                  type="button"
                  onClick={handleSubmit}
                  disabled={loading}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-emerald-500/20"
                >
                  <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                  {loading ? 'Extracting Vector...' : 'Save Biometric Template'}
                </Button>
              </>
            ) : (
              <Button
                type="button"
                onClick={handleCapture}
                className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-indigo-500/20"
              >
                <Camera className="h-3.5 w-3.5 mr-1.5" />
                Capture Photo
              </Button>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}

export default BiometricEnrollModal;
