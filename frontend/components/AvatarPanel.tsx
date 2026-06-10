"use client";

/**
 * AvatarPanel
 *
 * Renders the SadTalker Avatar Pipeline status tracker and controls.
 *
 * Workflow mirrors F5VoicePanel EXACTLY:
 *   1. User uploads a portrait photo via /upload-avatar-source.
 *   2. /generate-avatar exports the avatar package to Google Drive queue.
 *   3. Automated polling of /project/{id}/sadtalker-status tracks progress.
 *   4. Once clips are ready, refreshes parent to unlock Render button.
 *   5. Manual fallback: download ZIP → run SadTalker → upload clips ZIP.
 */

import { useRef, useState, useEffect, useCallback } from "react";
import {
  Upload,
  Download,
  CheckCircle,
  AlertCircle,
  Loader2,
  Clock,
  Cpu,
  ChevronDown,
  ChevronUp,
  User,
  ImageIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  uploadAvatarSource,
  generateAvatar,
  exportSadTalkerPackage,
  importSadTalkerClips,
  getSadTalkerStatus,
} from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

export interface AvatarResult {
  scene_id: number;
  clip_path: string;
  duration: number;
  provider: string;
}

export interface AvatarPanelProps {
  projectId: string;
  /** Current avatar_generation_status from project config ("pending" | "completed") */
  avatarStatus?: string;
  /** Whether the avatar package has already been exported */
  packageExported?: boolean;
  /** ISO-8601 timestamp of last successful clip import */
  avatarImportedAt?: string | null;
  /** Called after a successful clip import so the parent can refresh state */
  onImportComplete: (results: AvatarResult[]) => void;
}

type UploadState = "idle" | "uploading" | "success" | "error";

interface ValidationReport {
  status: string;
  scenes_detected: number;
  scenes_expected?: number;
  clips_imported: string[];
  avatar_results_generated: boolean;
  avatar_imported_at?: string;
}

// ── Component ────────────────────────────────────────────────────────────────

export function AvatarPanel({
  projectId,
  avatarStatus,
  packageExported,
  avatarImportedAt,
  onImportComplete,
}: AvatarPanelProps) {
  // ── Automated Queue Status State ──────────────────────────────────────────
  const [sadStatus, setSadStatus] = useState<string>("queued");
  const [queuedAt, setQueuedAt] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState<boolean>(true);
  const [errorStatus, setErrorStatus] = useState<string | null>(null);

  // ── Source Image Upload State ─────────────────────────────────────────────
  const [sourceUploaded, setSourceUploaded] = useState(false);
  const [sourceUploadState, setSourceUploadState] = useState<UploadState>("idle");
  const sourceFileRef = useRef<HTMLInputElement>(null);

  // ── Manual Fallback State ─────────────────────────────────────────────────
  const [showManualFallback, setShowManualFallback] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportDone, setExportDone] = useState(!!packageExported);
  const [clipsUploadState, setClipsUploadState] = useState<UploadState>("idle");
  const [clipsMsg, setClipsMsg] = useState("");
  const [clipsReport, setClipsReport] = useState<ValidationReport | null>(null);
  const clipsFileRef = useRef<HTMLInputElement>(null);

  // ── Poll Status ───────────────────────────────────────────────────────────
  const fetchStatus = useCallback(async () => {
    try {
      const data = await getSadTalkerStatus(projectId);
      setSadStatus(data.status);
      setQueuedAt(data.queued_at || null);
      setLastUpdate(data.last_update || null);
      setErrorStatus(null);

      if (data.clips_ready) {
        onImportComplete([]); // trigger parent refresh to unlock Render
      }
      return data.status;
    } catch (e) {
      console.error("Failed to fetch SadTalker status:", e);
      setErrorStatus("Failed to sync avatar queue status");
      return null;
    } finally {
      setLoadingStatus(false);
    }
  }, [projectId, onImportComplete]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(async () => {
      const status = await fetchStatus();
      if (status && status !== "queued" && status !== "processing") {
        clearInterval(interval);
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // ── Source Image Upload ───────────────────────────────────────────────────
  const handleSourceUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setSourceUploadState("uploading");
    try {
      await uploadAvatarSource(projectId, file);
      setSourceUploaded(true);
      setSourceUploadState("success");
      // Auto-trigger avatar package export
      await generateAvatar(projectId);
      setExportDone(true);
      fetchStatus();
    } catch (err) {
      setSourceUploadState("error");
      console.error("Source image upload failed:", err);
    } finally {
      if (sourceFileRef.current) sourceFileRef.current.value = "";
    }
  };

  // ── Manual Export ─────────────────────────────────────────────────────────
  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await exportSadTalkerPackage(projectId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sadtalker_pack_${projectId}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      setExportDone(true);
      fetchStatus();
    } catch (err) {
      console.error("Export failed:", err);
    } finally {
      setExporting(false);
    }
  };

  // ── Manual Clip Import ────────────────────────────────────────────────────
  const handleClipsUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setClipsUploadState("uploading");
    setClipsMsg("");
    setClipsReport(null);

    try {
      const result = await importSadTalkerClips(projectId, file);
      const report = result.validation_report as ValidationReport | undefined;
      setClipsReport(report ?? null);
      setClipsUploadState("success");
      setClipsMsg("Combined avatar video imported successfully.");
      onImportComplete(result.avatar_results);
      fetchStatus();
    } catch (err) {
      setClipsUploadState("error");
      setClipsMsg(err instanceof Error ? err.message : "Import failed.");
    } finally {
      if (clipsFileRef.current) clipsFileRef.current.value = "";
    }
  };

  // ── UI helpers ────────────────────────────────────────────────────────────
  const getStatusColor = () => {
    switch (sadStatus) {
      case "clips_ready":
      case "completed":
        return "border-violet-500/30 bg-violet-500/5 text-violet-300";
      case "processing":
        return "border-indigo-500/30 bg-indigo-500/5 text-indigo-300";
      case "failed":
        return "border-rose-500/30 bg-rose-500/5 text-rose-300";
      default:
        return "border-amber-500/30 bg-amber-500/5 text-amber-300";
    }
  };

  const getStatusLabel = () => {
    switch (sadStatus) {
      case "clips_ready":
      case "completed":
        return "Clips Ready";
      case "processing":
        return "Processing";
      case "failed":
        return "Failed";
      default:
        return "Queued";
    }
  };

  const isComplete = sadStatus === "clips_ready" || sadStatus === "completed";

  return (
    <div className={`rounded-xl border p-6 space-y-6 transition-all duration-300 ${getStatusColor()}`}>
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-1 shrink-0">
            <User className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <h3 className="font-semibold text-sm tracking-wide">
              SadTalker Avatar Generation
            </h3>
            <p className="text-xs text-white/50 mt-1">
              Google Drive path:{" "}
              <code className="bg-white/5 px-1 py-0.5 rounded text-white/70">
                WhiteboardAI_Avatar/
              </code>
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
                isComplete
                  ? "bg-violet-500/10 border-violet-500/30 text-violet-400"
                  : sadStatus === "processing"
                  ? "bg-indigo-500/10 border-indigo-500/30 text-indigo-400"
                  : sadStatus === "failed"
                  ? "bg-rose-500/10 border-rose-500/30 text-rose-400"
                  : "bg-amber-500/10 border-amber-500/30 text-amber-400"
              }`}
            >
              {getStatusLabel()}
            </span>
          )}
        </div>
      </div>

      {/* ── Step 1: Upload Portrait Photo ── */}
      <div className="p-4 rounded-lg bg-white/5 border border-white/10 space-y-3">
        <p className="text-xs font-semibold text-white/80 flex items-center gap-2">
          <ImageIcon className="w-3.5 h-3.5 text-violet-400" />
          Step 1: Upload Portrait Photo
        </p>
        <p className="text-xs text-white/40">
          Upload a clear, front-facing portrait photo. SadTalker will animate it
          to lip-sync with each scene's narration audio.
        </p>
        <div className="flex items-center gap-3">
          <input
            ref={sourceFileRef}
            id="avatar-source-input"
            type="file"
            accept=".png,.jpg,.jpeg,.webp,image/*"
            className="hidden"
            onChange={handleSourceUpload}
            disabled={sourceUploadState === "uploading"}
          />
          <Button
            id="avatar-source-btn"
            variant="outline"
            size="sm"
            onClick={() => sourceFileRef.current?.click()}
            disabled={sourceUploadState === "uploading"}
            className="border-violet-500/30 text-violet-300 hover:bg-violet-500/10"
          >
            {sourceUploadState === "uploading" ? (
              <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
            ) : (
              <Upload className="w-3.5 h-3.5 mr-2" />
            )}
            Upload Portrait
          </Button>
          {sourceUploadState === "success" && (
            <span className="text-xs text-violet-400 flex items-center gap-1">
              <CheckCircle className="w-3.5 h-3.5" /> Uploaded &amp; package exported
            </span>
          )}
          {sourceUploadState === "error" && (
            <span className="text-xs text-rose-400 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" /> Upload failed
            </span>
          )}
        </div>
      </div>

      {/* ── Progress Steps ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-3 bg-white/5 rounded-lg border border-white/10 space-y-1">
          <div className="text-xs text-white/40 flex items-center justify-between">
            <span>Step 2: Enqueued</span>
            <Clock className="w-3.5 h-3.5" />
          </div>
          <p className="text-xs font-semibold text-white/80">Package on Drive</p>
          {queuedAt && (
            <p className="text-[10px] text-white/40">
              {new Date(queuedAt).toLocaleTimeString()}
            </p>
          )}
        </div>

        <div
          className={`p-3 rounded-lg border space-y-1 ${
            sadStatus === "processing" || isComplete
              ? "bg-indigo-500/5 border-indigo-500/20"
              : "bg-white/5 border-white/10 opacity-50"
          }`}
        >
          <div className="text-xs text-white/40 flex items-center justify-between">
            <span>Step 3: Processing</span>
            <Cpu className="w-3.5 h-3.5" />
          </div>
          <p className="text-xs font-semibold text-white/80">Colab generating clips</p>
          {sadStatus === "processing" && (
            <span className="text-[10px] text-indigo-400 animate-pulse flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" /> Synthesizing avatar…
            </span>
          )}
        </div>

        <div
          className={`p-3 rounded-lg border space-y-1 ${
            isComplete
              ? "bg-violet-500/5 border-violet-500/20"
              : "bg-white/5 border-white/10 opacity-50"
          }`}
        >
          <div className="text-xs text-white/40 flex items-center justify-between">
            <span>Step 4: Clips Ready</span>
            <CheckCircle className="w-3.5 h-3.5" />
          </div>
          <p className="text-xs font-semibold text-white/80">Imported &amp; ready to render</p>
          {isComplete && lastUpdate && (
            <p className="text-[10px] text-violet-400">
              Synced: {new Date(lastUpdate).toLocaleTimeString()}
            </p>
          )}
        </div>
      </div>

      {/* ── Status Banners ── */}
      {sadStatus === "failed" && (
        <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 px-4 py-3 text-xs text-rose-300 flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">SadTalker generation or import failed.</p>
            <p className="text-white/60 mt-0.5">
              Check the Colab worker logs or use the manual fallback below.
            </p>
          </div>
        </div>
      )}

      {isComplete && (
        <div className="rounded-lg bg-violet-500/10 border border-violet-500/20 px-4 py-3 text-xs text-violet-300 flex items-start gap-2.5">
          <CheckCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Avatar sync complete!</p>
            <p className="text-white/60 mt-0.5">
              Talking-head clips have been imported. Click{" "}
              <strong>Render Video</strong> to compose the final animation.
            </p>
          </div>
        </div>
      )}

      {/* ── Manual Fallback ── */}
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
              If the Google Drive automated watcher is offline, download the
              package, run SadTalker locally, then upload the WebM clips ZIP.
            </p>

            <div className="space-y-3 pl-2">
              {/* Download Package */}
              <div>
                <p className="font-semibold text-white/90">1. Download Avatar Package</p>
                <div className="mt-1.5 flex items-center gap-3">
                  <Button
                    id="sadtalker-export-btn"
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
                    <span className="text-xs text-green-400 flex items-center gap-1">
                      <CheckCircle className="w-3.5 h-3.5" /> Exported
                    </span>
                  )}
                </div>
              </div>

              {/* Run SadTalker */}
              <div>
                <p className="font-semibold text-white/90">2. Run SadTalker Externally</p>
                <p className="text-white/40 mt-0.5">
                  Generate <code>avatar.webm</code> (transparent WebM
                  with VP9+alpha) driven by the full project combined narration, and zip it.
                </p>
              </div>

              {/* Upload Clips ZIP */}
              <div>
                <p className="font-semibold text-white/90">3. Upload Clips ZIP</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-3">
                  <input
                    ref={clipsFileRef}
                    id="sadtalker-clips-input"
                    type="file"
                    accept=".zip,application/zip"
                    className="hidden"
                    onChange={handleClipsUpload}
                    disabled={clipsUploadState === "uploading"}
                  />
                  <Button
                    id="sadtalker-import-btn"
                    variant="outline"
                    size="sm"
                    onClick={() => clipsFileRef.current?.click()}
                    disabled={clipsUploadState === "uploading"}
                    className="border-white/20 text-white/80 hover:bg-white/5"
                  >
                    {clipsUploadState === "uploading" ? (
                      <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                    ) : (
                      <Upload className="w-3.5 h-3.5 mr-2" />
                    )}
                    Upload Clips ZIP
                  </Button>

                  {clipsUploadState === "success" && (
                    <span className="text-xs text-green-400 flex items-center gap-1">
                      <CheckCircle className="w-3.5 h-3.5" /> {clipsMsg}
                    </span>
                  )}
                  {clipsUploadState === "error" && (
                    <span className="text-xs text-red-400 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" /> {clipsMsg}
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
