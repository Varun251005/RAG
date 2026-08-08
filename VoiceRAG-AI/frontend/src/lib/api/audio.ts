const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface TranscribeResponse {
  text: string;
  language: string;
  duration_seconds: number;
  confidence: number;
}

export async function transcribeAudio(audioBlob: Blob): Promise<TranscribeResponse> {
  const formData = new FormData();
  const extension = audioBlob.type.includes("webm")
    ? "webm"
    : audioBlob.type.includes("mp4")
    ? "mp4"
    : audioBlob.type.includes("ogg")
    ? "ogg"
    : "wav";

  formData.append("file", audioBlob, `recording.${extension}`);

  const response = await fetch(`${API_BASE_URL}/api/v1/audio/transcribe`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let detail = `Server responded with status ${response.status}`;
    try {
      const err = await response.json();
      if (err.detail) detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    } catch {
      // Fallback
    }
    throw new Error(detail);
  }

  return (await response.json()) as TranscribeResponse;
}
