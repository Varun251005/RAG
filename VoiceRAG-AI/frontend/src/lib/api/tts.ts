import { TTSVoicesResponse } from "@/types/tts";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchTTSVoices(): Promise<TTSVoicesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/tts/voices`);
  if (!response.ok) {
    throw new Error("Failed to fetch TTS voices");
  }
  return (await response.json()) as TTSVoicesResponse;
}

export async function getTTSAudioStreamUrl(
  text: string,
  voice: string = "en-US-AriaNeural",
  rate: string = "+0%"
): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/v1/tts/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      text,
      voice,
      rate,
    }),
  });

  if (!response.ok) {
    let detail = `TTS failed with status ${response.status}`;
    try {
      const err = await response.json();
      if (err.detail) detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    } catch {
      // Fallback
    }
    throw new Error(detail);
  }

  const audioBlob = await response.blob();
  return URL.createObjectURL(audioBlob);
}
