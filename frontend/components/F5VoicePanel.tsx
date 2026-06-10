"use client";

/**
 * F5VoicePanel
 *
 * Renders the F5-TTS Google Drive Queue Automation status tracker.
 *
 * Workflow:
 *   1. Displays current processing status in the Google Drive Queue (Queued, Processing, Audio Ready, Failed).
 *   2. Periodically polls the GET /project/{id}/f5-status API when in Queued or Processing state.
 *   3. Once Audio Ready, refreshes parent component to unlock the Render button.
 *   4. Provides a collapsible "Manual Upload Fallback" section in case Google Drive sync is offline.
 */

import { useRef, useState, useEffect, useCallback } from "react";
import {
  Download,
  Upload,
  CheckCircle,
  AlertCircle,
  Loader2,
  Clock,
  Cpu,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { exportF5Package, importF5Audio, getF5Status } from "@/lib/api";
import type { VoiceResult } from "@/lib/api";

interface F5VoicePanelProps {
  projectId: string;
  /** Current voice_generation_status from project config ("pending" | "completed") */
  voiceStatus?: string;
  /** Whether the narration package has already been exported */
  packageExported?: boolean;
  /** ISO-8601 timestamp of last successful import (for audit display) */
  audioImportedAt?: string | null;
  /** Called after a successful audio import so the parent can refresh state */
  onImportComplete: (results: VoiceResult[]) => void;
}

type ImportState = "idle" | "uploading" | "success" | "error";

interface ValidationReport {
  status: string;
  scenes_detected: number;
  scenes_expected: number;
  combined_audio_generated: boolean;
  voice_results_generated: boolean;
  audio_imported_at?: string;
  durations?: Record<string, number>;
}

export function F5VoicePanel({
  projectId,
  voiceStatus,
  packageExported,
  audioImportedAt,
  onImportComplete,
}: F5VoicePanelProps) {
  // Automated Queue Status State
  const [f5Status, setF5Status] = useState<string>("queued");
  const [queuedAt, setQueuedAt] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState<boolean>(true);
  const [errorStatus, setErrorStatus] = useState<string | null>(null);

  // Fallback Manual UI State
  const [showManualFallback, setShowManualFallback] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportDone, setExportDone] = useState(!!packageExported);
  const [importState, setImportState] = useState<ImportState>("idle");
  const [importMsg, setImportMsg] = useState("");
  const [importReport, setImportReport] = useState<ValidationReport | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Poll status from the API
  const fetchStatus = useCallback(async () => {
    try {
      const data = await getF5Status(projectId);
      setF5Status(data.status);
      setQueuedAt(data.queued_at || null);
      setLastUpdate(data.last_update || null);
      setErrorStatus(null);

      if (data.audio_ready) {
        onImportComplete([]); // Trigger parent refresh to unlock render button
      }
      return data.status;
    } catch (e) {
      console.error("Failed to fetch F5 status:", e);
      setErrorStatus("Failed to sync queue status");
      return null;
    } finally {
      setLoadingStatus(false);
    }
  }, [projectId, onImportComplete]);

  // Start/Stop polling based on status
  useEffect(() => {
    fetchStatus();

    // Set up polling interval every 5 seconds if queued or processing
    const interval = setInterval(async () => {
      const status = await fetchStatus();
      if (status && status !== "queued" && status !== "processing") {
        clearInterval(interval);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await exportF5Package(projectId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `narration_pack_${projectId}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      setExportDone(true);
      fetchStatus();
    } catch (e) {
      console.error("Export failed:", e);
    } finally {
      setExporting(false);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImportState("uploading");
    setImportMsg("");
    setImportReport(null);

    try {
      const result = await importF5Audio(projectId, file);
      const report = result.validation_report as ValidationReport | undefined;
      setImportReport(report ?? null);
      const count = report?.scenes_detected ?? result.voice_results.length;
      setImportState("success");
      setImportMsg(`${count} scene${count !== 1 ? "s" : ""} imported successfully.`);
      onImportComplete(result.voice_results);
      fetchStatus();
    } catch (e) {
      setImportState("error");
      setImportMsg(e instanceof Error ? e.message : "Import failed.");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  // UI helpers for status display
  const getStatusColor = () => {
    switch (f5Status) {
      case "audio_ready":
      case "completed":
        return "border-emerald-500/30 bg-emerald-500/5 text-emerald-300";
      case "processing":
        return "border-sky-500/30 bg-sky-500/5 text-sky-300";
      case "failed":
        return "border-rose-500/30 bg-rose-500/5 text-rose-300";
      case "queued":
      default:
        return "border-amber-500/30 bg-amber-500/5 text-amber-300";
    }
  };

  const getStatusLabel = () => {
    switch (f5Status) {
      case "audio_ready":
      case "completed":
        return "Audio Ready";
      case "processing":
        return "Processing";
      case "failed":
        return "Failed";
      case "queued":
      default:
        return "Queued";
    }
  };

  return (
    <div className={`rounded-xl border p-6 space-y-6 transition-all duration-300 ${getStatusColor()}`}>
      {/* Header and Live Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-1 shrink-0">
            {f5Status === "queued" && <Clock className="w-5 h-5 animate-pulse text-amber-400" />}
            {f5Status === "processing" && <Cpu className="w-5 h-5 animate-spin text-sky-400" />}
            {(f5Status === "audio_ready" || f5Status === "completed") && (
              <CheckCircle className="w-5 h-5 text-emerald-400" />
            )}
            {f5Status === "failed" && <AlertCircle className="w-5 h-5 text-rose-400" />}
          </div>
          <div>
            <h3 className="font-semibold text-sm tracking-wide">
              F5-TTS Voice Automation Queue
            </h3>
            <p className="text-xs text-white/50 mt-1">
              Google Drive path: <code className="bg-white/5 px-1 py-0.5 rounded text-white/70">WhiteboardAI/</code>
            </p>
          </div>
        </div>

        {/* Status Badge */}
        <div className="flex items-center gap-3 self-start sm:self-center">
          {loadingStatus ? (
            <span className="text-xs text-white/40 flex items-center gap-1.5 bg-white/5 px-3 py-1.5 rounded-full">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Syncing...
            </span>
          ) : (
            <span
              className={`text-xs font-bold px-3.5 py-1.5 rounded-full uppercase tracking-wider shadow-sm border ${
                f5Status === "audio_ready" || f5Status === "completed"
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                  : f5Status === "processing"
                  ? "bg-sky-500/10 border-sky-500/30 text-sky-400"
                  : f5Status === "failed"
                  ? "bg-rose-500/10 border-rose-500/30 text-rose-400"
                  : "bg-amber-500/10 border-amber-500/30 text-amber-400"
              }`}
            >
              {getStatusLabel()}
            </span>
          )}
        </div>
      </div>

      {/* Progress Steps Visual Indicator */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
        {/* Step 1: Queued */}
        <div className="p-3 bg-white/5 rounded-lg border border-white/10 space-y-1">
          <div className="text-xs text-white/40 flex items-center justify-between">
            <span>Step 1: Enqueued</span>
            <Clock className="w-3.5 h-3.5" />
          </div>
          <p className="text-xs font-semibold text-white/80">Narration pack on Drive</p>
          {queuedAt && (
            <p className="text-[10px] text-white/40">
              {new Date(queuedAt).toLocaleTimeString()}
            </p>
          )}
        </div>

        {/* Step 2: Processing */}
        <div
          className={`p-3 rounded-lg border space-y-1 ${
            f5Status === "processing" || f5Status === "audio_ready" || f5Status === "completed"
              ? "bg-sky-500/5 border-sky-500/20"
              : "bg-white/5 border-white/10 opacity-50"
          }`}
        >
          <div className="text-xs text-white/40 flex items-center justify-between">
            <span>Step 2: Processing</span>
            <Cpu className="w-3.5 h-3.5" />
          </div>
          <p className="text-xs font-semibold text-white/80">Colab Worker generating</p>
          {f5Status === "processing" && (
            <span className="text-[10px] text-sky-400 animate-pulse flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" /> Synthesizing audio...
            </span>
          )}
        </div>

        {/* Step 3: Audio Ready */}
        <div
          className={`p-3 rounded-lg border space-y-1 ${
            f5Status === "audio_ready" || f5Status === "completed"
              ? "bg-emerald-500/5 border-emerald-500/20"
              : "bg-white/5 border-white/10 opacity-50"
          }`}
        >
          <div className="text-xs text-white/40 flex items-center justify-between">
            <span>Step 3: Completed</span>
            <CheckCircle className="w-3.5 h-3.5" />
          </div>
          <p className="text-xs font-semibold text-white/80">Imported & ready to render</p>
          {(f5Status === "audio_ready" || f5Status === "completed") && lastUpdate && (
            <p className="text-[10px] text-emerald-400">
              Synced: {new Date(lastUpdate).toLocaleTimeString()}
            </p>
          )}
        </div>
      </div>

      {/* Failure Info */}
      {f5Status === "failed" && (
        <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 px-4 py-3 text-xs text-rose-300 flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Colab generation or import failed.</p>
            <p className="text-white/60 mt-0.5">
              Please check the Colab worker logs or try exporting the package again to retry.
            </p>
          </div>
        </div>
      )}

      {/* Success Info Banner */}
      {(f5Status === "audio_ready" || f5Status === "completed") && (
        <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-4 py-3 text-xs text-emerald-300 flex items-start gap-2.5">
          <CheckCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Automation sync complete!</p>
            <p className="text-white/60 mt-0.5">
              The project voice files have been successfully generated and imported. Click the{" "}
              <strong>Render Video</strong> button at the top to compile your animation.
            </p>
          </div>
        </div>
      )}

      {/* Manual Fallback Collapsible */}
      <div className="border-t border-white/10 pt-4">
        <button
          onClick={() => setShowManualFallback(!showManualFallback)}
          className="flex items-center gap-1.5 text-xs text-white/40 hover:text-white/70 transition-colors focus:outline-none"
        >
          {showManualFallback ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
          Manual Upload Fallback (Offline Mode)
        </button>

        {showManualFallback && (
          <div className="mt-4 p-4 rounded-lg bg-white/5 border border-white/10 space-y-4 text-xs text-white/70">
            <p className="text-white/50">
              If the Google Drive automated watcher is offline, you can still export the package and
              upload the generated voice ZIP manually.
            </p>

            <div className="space-y-3 pl-2">
              {/* Step 1 */}
              <div>
                <p className="font-semibold text-white/90">1. Export Narration Package</p>
                <div className="mt-1.5 flex items-center gap-3">
                  <Button
                    id="f5-export-btn"
                    variant="outline"
                    size="sm"
                    onClick={handleExport}
                    disabled={exporting}
                    className="border-white/20 text-white/80 hover:bg-white/5"
                  >
                    {exporting ? (
                      <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5 mr-2" />
                    )}
                    Download Package ZIP
                  </Button>
                  {exportDone && (
                    <span className="text-xs text-green-400 inline-flex items-center gap-1">
                      <CheckCircle className="w-3.5 h-3.5" /> Exported
                    </span>
                  )}
                </div>
              </div>

              {/* Step 2 */}
              <div>
                <p className="font-semibold text-white/90">2. Run F5-TTS Externally</p>
                <p className="text-white/40 mt-0.5">
                  Generate <code>scene_1.wav</code>, <code>scene_2.wav</code>... and zip them.
                </p>
              </div>

              {/* Step 3 */}
              <div>
                <p className="font-semibold text-white/90">3. Upload F5 audio ZIP</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-3">
                  <input
                    ref={fileRef}
                    id="f5-audio-zip-input"
                    type="file"
                    accept=".zip,application/zip"
                    className="hidden"
                    onChange={handleFileChange}
                    disabled={importState === "uploading"}
                  />
                  <Button
                    id="f5-import-btn"
                    variant="outline"
                    size="sm"
                    onClick={() => fileRef.current?.click()}
                    disabled={importState === "uploading"}
                    className="border-white/20 text-white/80 hover:bg-white/5"
                  >
                    {importState === "uploading" ? (
                      <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                    ) : (
                      <Upload className="w-3.5 h-3.5 mr-2" />
                    )}
                    Upload ZIP
                  </Button>

                  {importState === "success" && (
                    <span className="text-xs text-green-400 inline-flex items-center gap-1">
                      <CheckCircle className="w-3.5 h-3.5" /> {importMsg}
                    </span>
                  )}
                  {importState === "error" && (
                    <span className="text-xs text-red-400 inline-flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" /> {importMsg}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
