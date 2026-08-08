"use client";

import React from "react";
import { Volume2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TTSVoice } from "@/types/tts";

interface VoiceSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  voices: TTSVoice[];
  selectedVoice: string;
  onSelectVoice: (voice: string) => void;
  speechRate: string;
  onSelectRate: (rate: string) => void;
}

const DEFAULT_VOICES: TTSVoice[] = [
  { name: "Microsoft Ava Online (Natural) - English (United States)", short_name: "en-US-AvaNeural", gender: "Female", locale: "en-US" },
  { name: "Microsoft Aria Online (Natural) - English (United States)", short_name: "en-US-AriaNeural", gender: "Female", locale: "en-US" },
  { name: "Microsoft Guy Online (Natural) - English (United States)", short_name: "en-US-GuyNeural", gender: "Male", locale: "en-US" },
  { name: "Microsoft Jenny Online (Natural) - English (United States)", short_name: "en-US-JennyNeural", gender: "Female", locale: "en-US" },
  { name: "Microsoft Sonia Online (Natural) - English (United Kingdom)", short_name: "en-GB-SoniaNeural", gender: "Female", locale: "en-GB" },
  { name: "Microsoft Ryan Online (Natural) - English (United Kingdom)", short_name: "en-GB-RyanNeural", gender: "Male", locale: "en-GB" },
];

const RATES = [
  { label: "0.8x (Slower)", value: "-20%" },
  { label: "1.0x (Normal)", value: "+0%" },
  { label: "1.2x (Faster)", value: "+20%" },
  { label: "1.5x (Fast)", value: "+50%" },
];

export function VoiceSettingsModal({
  isOpen,
  onClose,
  voices,
  selectedVoice,
  onSelectVoice,
  speechRate,
  onSelectRate,
}: VoiceSettingsModalProps) {
  if (!isOpen) return null;

  const displayVoices = voices && voices.length > 0 ? voices : DEFAULT_VOICES;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-white border border-zinc-200 rounded-2xl max-w-md w-full p-6 shadow-xl space-y-6 relative text-zinc-900">
        <button
          onClick={onClose}
          type="button"
          className="absolute top-5 right-5 p-1 rounded-md text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-zinc-100 text-zinc-900 border border-zinc-200">
            <Volume2 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold tracking-tight text-zinc-900">Voice Output Settings</h2>
            <p className="text-xs text-zinc-500 mt-0.5">Configure Edge-TTS neural voice and speech rate</p>
          </div>
        </div>

        {/* Voice Selection */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-zinc-800">Neural Voice</label>
          <div className="relative">
            <select
              value={selectedVoice}
              onChange={(e) => onSelectVoice(e.target.value)}
              className="w-full rounded-xl border border-zinc-200 bg-white px-3 py-2.5 text-xs font-medium text-zinc-900 focus:outline-none focus:ring-2 focus:ring-zinc-900/10 focus:border-zinc-900 transition-all appearance-none cursor-pointer pr-8"
            >
              {displayVoices.map((v) => (
                <option key={v.short_name} value={v.short_name}>
                  {v.name} ({v.locale})
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400">
              ▼
            </div>
          </div>
        </div>

        {/* Speech Speed Rate Selection */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-zinc-800">Speech Speed Rate</label>
          <div className="grid grid-cols-2 gap-2.5">
            {RATES.map((r) => {
              const isSelected = speechRate === r.value;
              return (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => onSelectRate(r.value)}
                  className={`px-3 py-2.5 rounded-xl text-xs font-medium border text-center transition-all ${
                    isSelected
                      ? "bg-zinc-900 text-white border-zinc-900 shadow-sm"
                      : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-50"
                  }`}
                >
                  {r.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Save & Close Full Width Button */}
        <div className="pt-2">
          <Button
            onClick={onClose}
            className="w-full h-11 bg-zinc-900 hover:bg-zinc-800 text-white rounded-xl font-semibold text-xs transition-colors shadow-sm"
          >
            Save & Close
          </Button>
        </div>
      </div>
    </div>
  );
}

