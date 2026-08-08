import apiClient from "./client";

export interface ChatApiSource {
  document_id: string;
  filename: string;
  page_number: number;
  chunk_id: string;
}

export interface ChatApiResponse {
  answer: string;
  sources: ChatApiSource[];
}

export interface ChatApiRequest {
  question: string;
  document_id?: string | null;
}

/**
 * Send a question to POST /api/v1/chat and receive answer with source citations.
 */
export async function sendChatQuestion(
  question: string,
  documentId?: string | null
): Promise<ChatApiResponse> {
  const response = await apiClient.post<ChatApiResponse>("/api/v1/chat", {
    question: question.trim(),
    document_id: documentId || null,
  });
  return response.data;
}
