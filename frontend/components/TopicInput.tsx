"use client";

import { Input } from "./ui/input";

const EXAMPLES = [
  "Newton Laws",
  "Photosynthesis",
  "Binary Search",
  "Respiration",
  "TCP Handshake",
];

interface TopicInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function TopicInput({ value, onChange }: TopicInputProps) {
  return (
    <div className="space-y-4">
      <Input
        placeholder="Enter a topic, e.g. Newton Laws"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="text-lg h-14"
      />
      <div className="flex flex-wrap gap-2">
        <span className="text-sm text-white/50 w-full">Try an example:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => onChange(ex)}
            className="px-3 py-1.5 text-sm rounded-full bg-white/10 hover:bg-brand-600/30 border border-white/10 transition-colors"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
