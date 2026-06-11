"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Video, Clock, Mic } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TopicInput } from "@/components/TopicInput";
import { generateScript, renderVideo } from "@/lib/api";
import type { VoiceProvider } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [duration, setDuration] = useState(60);
  const [style, setStyle] = useState("whiteboard");
  const [voice, setVoice] = useState("male");
  const [voiceProvider, setVoiceProvider] = useState<VoiceProvider>("edge");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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
        voice_provider: voiceProvider,
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
        voice_provider: voiceProvider,
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
            Each scene: gpt-image-1-mini PNG → object-wise stroke reveal (storyboard-ai style).
          </p>

          <div className="space-y-2">
            <label className="text-sm text-white/70">Voice provider</label>
            <select
              id="voice-provider-select"
              value={voiceProvider}
              onChange={(e) => setVoiceProvider(e.target.value as VoiceProvider)}
              className="w-full h-10 rounded-lg bg-white/5 border border-white/20 px-3 text-white"
            >
              <option value="edge">Edge-TTS (instant, local)</option>
              <option value="f5tts">F5-TTS (export → external → import)</option>
            </select>
            {voiceProvider === "f5tts" && (
              <p className="text-xs text-amber-400/80">
                ⚠ F5-TTS mode: narration package will be exported. Upload WAV
                audio on the project page before rendering.
              </p>
            )}
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
