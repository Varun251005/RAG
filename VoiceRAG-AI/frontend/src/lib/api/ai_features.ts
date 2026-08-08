const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type AIFeatureType = "summary" | "flashcards" | "quiz" | "notes" | "key_topics" | "faq";

export interface AIFeatureResponse {
  question: string;
  answer: string;
  sources: Array<{
    chunk_id: string;
    snippet: string;
    page_number: number;
    original_filename: string;
    score: number;
    document_id: string;
  }>;
  total_chunks_used: number;
  model: string;
}

export async function fetchAIFeature(
  feature: AIFeatureType,
  documentId?: string | null
): Promise<AIFeatureResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/rag/ai-features`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      feature,
      document_id: documentId || null,
    }),
  });

  if (!response.ok) {
    let detail = `Failed to generate ${feature}`;
    try {
      const err = await response.json();
      if (err.detail) detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    } catch {
      // Fallback
    }
    throw new Error(detail);
  }

  return (await response.json()) as AIFeatureResponse;
}
