import { Suspense } from "react";
import { RenderPageInner } from "./RenderPageInner";

export default function RenderPage() {
  return (
    <main className="min-h-screen bg-slate-900">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <Suspense fallback={<div className="text-white/50">Loading...</div>}>
          <RenderPageInner />
        </Suspense>
      </div>
    </main>
  );
}
