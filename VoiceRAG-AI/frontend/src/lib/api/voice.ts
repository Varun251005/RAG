import apiClient from "./client";

export interface VoiceTranscribeApiResponse {
  text: string;
  language: string;
  duration: number;
}

export interface VoiceSynthesizeApiRequest {
  text: string;
  voice?: string;
}

/**
 * Send recorded audio blob to POST /api/v1/voice/transcribe.
 */
export async function transcribeVoiceAudio(
  audioBlob: Blob
): Promise<VoiceTranscribeApiResponse> {
  const extension = audioBlob.type.includes("webm")
    ? "webm"
    : audioBlob.type.includes("mp4") || audioBlob.type.includes("m4a")
    ? "m4a"
    : audioBlob.type.includes("ogg")
    ? "ogg"
    : "wav";

  const formData = new FormData();
  formData.append("file", audioBlob, `recording.${extension}`);

  const response = await apiClient.post<VoiceTranscribeApiResponse>(
    "/api/v1/voice/transcribe",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
    }
  );

  return response.data;
}

/**
 * Send text payload to POST /api/v1/voice/synthesize and return audio MP3 Blob.
 */
export async function synthesizeVoiceSpeech(
  request: VoiceSynthesizeApiRequest
): Promise<Blob> {
  const response = await apiClient.post("/api/v1/voice/synthesize", request, {
    responseType: "blob",
    headers: { "Content-Type": "application/json" },
  });

  return response.data;
}
