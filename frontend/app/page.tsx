"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Video, Clock, Mic } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TopicInput } from "@/components/TopicInput";
import { generateScript, renderVideo } from "@/lib/api";
import type { VoiceProvider } from "@/lib/types";
const LANGUAGE_OPTIONS = [
  { label: "English", value: "english" },
  { label: "Hindi", value: "hindi" },
  { label: "Hinglish (Roman + Hindi mix)", value: "hinglish" }
];

export default function HomePage() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [duration, setDuration] = useState(60);
  const [style, setStyle] = useState("whiteboard");
  const [voice, setVoice] = useState("male");
  const [ttsProvider, setTtsProvider] = useState<string>("f5tts");
  const [languageMode, setLanguageMode] = useState("english");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLanguageChange = (val: string) => {
    setLanguageMode(val);
    if (val === "hindi" || val === "hinglish") {
      setTtsProvider("xtts_hindi");
    } else {
      setTtsProvider("f5tts");
    }
  };

  const handleGenerate = async () => {
    if (!topic.trim()) {
      setError("Please enter a topic");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const { project_id } = await generateScript({
        topic: topic.trim(),
        duration,
        style,
        voice,
        language: "english",
        language_mode: languageMode,
        voice_provider: ttsProvider === "f5tts" ? "f5tts" : ttsProvider === "xtts_hindi" ? "xtts_hindi" : "edge",
        tts_provider: ttsProvider,
        avatar_provider: null,
      });
      const { job_id } = await renderVideo(project_id);
      router.push(`/render/${project_id}?job=${job_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async () => {
    if (!topic.trim()) {
      setError("Please enter a topic");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const { project_id } = await generateScript({
        topic: topic.trim(),
        duration,
        style,
        voice,
        language: "english",
        language_mode: languageMode,
        voice_provider: ttsProvider === "f5tts" ? "f5tts" : ttsProvider === "xtts_hindi" ? "xtts_hindi" : "edge",
        tts_provider: ttsProvider,
        avatar_provider: null,
      });
      router.push(`/project/${project_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen">
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-brand-600/10 via-transparent to-transparent" />

      <div className="relative max-w-4xl mx-auto px-6 py-16">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-600/20 border border-brand-500/30 text-brand-300 text-sm mb-6">
            <Sparkles className="w-4 h-4" />
            AI Educational Whiteboard Videos
          </div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
            Turn Any Topic Into a
            <span className="text-brand-400"> Whiteboard Video</span>
          </h1>
          <p className="text-lg text-white/60 max-w-2xl mx-auto">
            GPT-generated whiteboard sketches per scene, stroke-reveal animation, voice, and MP4 — all local.
          </p>
        </div>

        <Card className="space-y-8">
          <TopicInput value={topic} onChange={setTopic} />

          <p className="text-xs text-white/40 -mt-4">
            Each scene: gpt-image-1-mini PNG → Vision bboxes → contour SVG stroke reveal.
          </p>

          <div className="space-y-2">
            <label className="text-sm text-white/70">Narration Engine</label>
            <select
              id="tts-provider-select"
              value={ttsProvider}
              onChange={(e) => setTtsProvider(e.target.value)}
              disabled={languageMode === "hindi" || languageMode === "hinglish"}
              className="w-full h-10 rounded-lg bg-white/5 border border-white/20 px-3 text-white disabled:opacity-50"
            >
              {languageMode === "english" ? (
                <>
                  <option value="f5tts">F5-TTS (export → external → import)</option>
                  <option value="edge_tts">Edge-TTS (instant, local)</option>
                </>
              ) : (
                <option value="xtts_hindi">XTTS Hindi (local, voice cloning)</option>
              )}
            </select>
            {languageMode === "english" && ttsProvider === "f5tts" && (
              <p className="text-xs text-amber-400/80">
                ⚠ F5-TTS mode: narration package will be exported. Upload WAV
                audio on the project page before rendering.
              </p>
            )}
            {(languageMode === "hindi" || languageMode === "hinglish") && (
              <p className="text-xs text-emerald-400/80">
                ✓ XTTS Hindi uses your teacher reference voice for cloning. Runs locally on CPU.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <label className="text-sm text-white/70">Narration Language</label>
            <select
              id="language-mode-select"
              value={languageMode}
              onChange={(e) => handleLanguageChange(e.target.value)}
              className="w-full h-10 rounded-lg bg-white/5 border border-white/20 px-3 text-white"
            >

              {LANGUAGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-white/50">
              {languageMode === "english"
                ? "Audio narration will be fully English."
                : languageMode === "hindi"
                ? "Audio narration will be spoken in pure Hindi (Devanagari). On-screen content remains English."
                : "Audio narration will be spoken in conversational Hinglish while all on-screen content remains English."}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm text-white/70">
                <Clock className="w-4 h-4" /> Duration
              </label>
              <input
                type="range"
                min={30}
                max={180}
                step={15}
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                className="w-full accent-brand-500"
              />
              <span className="text-sm text-white/50">{duration} seconds</span>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-white/70">Style</label>
              <select
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                className="w-full h-10 rounded-lg bg-white/5 border border-white/20 px-3 text-white"
              >
                <option value="whiteboard">Whiteboard</option>
                <option value="minimal">Minimal</option>
                <option value="colorful">Colorful</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm text-white/70">
                <Mic className="w-4 h-4" /> Voice
              </label>
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="w-full h-10 rounded-lg bg-white/5 border border-white/20 px-3 text-white"
              >
                <option value="male">Male (US)</option>
                <option value="female">Female (US)</option>
                <option value="male_uk">Male (UK)</option>
                <option value="female_uk">Female (UK)</option>
              </select>
            </div>
          </div>

          {error && (
            <p className="text-red-400 text-sm bg-red-400/10 px-4 py-2 rounded-lg">
              {error}
            </p>
          )}

          <div className="flex flex-col sm:flex-row gap-4">
            <Button
              size="lg"
              className="flex-1"
              onClick={handleGenerate}
              disabled={loading}
            >
              <Video className="w-5 h-5 mr-2" />
              {loading ? "Starting..." : "Generate Full Video"}
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="flex-1"
              onClick={handlePreview}
              disabled={loading}
            >
              Preview Script First
            </Button>
          </div>
        </Card>

        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
          {[
            { title: "Script + Scenes", desc: "OpenAI writes the lesson scene-by-scene" },
            { title: "AI Sketches", desc: "gpt-image-1-mini PNG per scene, stroke reveal" },
            { title: "Local Render", desc: "Remotion + FFmpeg on your machine" },
          ].map((f) => (
            <div key={f.title} className="glass rounded-xl p-6">
              <h3 className="font-semibold text-brand-300 mb-2">{f.title}</h3>
              <p className="text-sm text-white/50">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
