import { SourceCitation } from "@/types/chat";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface StreamQueryOptions {
  question: string;
  documentId?: string | null;
  topK?: number;
  signal?: AbortSignal;
  onToken: (text: string) => void;
  onSources: (sources: SourceCitation[]) => void;
  onDone: () => void;
  onError: (errorDetail: string) => void;
}

export async function streamRagQuery({
  question,
  documentId,
  topK = 5,
  signal,
  onToken,
  onSources,
  onDone,
  onError,
}: StreamQueryOptions): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/rag/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({
        question,
        top_k: topK,
        document_id: documentId || null,
      }),
      signal,
    });

    if (!response.ok) {
      let detail = `Server responded with status ${response.status}`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          detail = typeof errorJson.detail === "string" ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fallback to default message
      }
      onError(detail);
      return;
    }

    if (!response.body) {
      onError("Response body is empty.");
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentEvent = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        if (trimmed.startsWith("event:")) {
          currentEvent = trimmed.substring(6).trim();
        } else if (trimmed.startsWith("data:")) {
          const dataStr = trimmed.substring(5).trim();
          try {
            const data = JSON.parse(dataStr);
            if (currentEvent === "token" && data.text) {
              onToken(data.text);
            } else if (currentEvent === "sources" && data.sources) {
              onSources(data.sources as SourceCitation[]);
            } else if (currentEvent === "done") {
              onDone();
            } else if (currentEvent === "error") {
              onError(data.detail || "An error occurred during generation.");
            }
          } catch (e) {
            console.error("Failed to parse SSE data:", dataStr, e);
          }
        }
      }
    }

    onDone();
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") {
      console.log("Stream aborted by user");
      return;
    }
    const message = err instanceof Error ? err.message : "Failed to connect to the assistant service.";
    onError(message);
  }
}

export async function ingestDocument(docId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/v1/rag/ingest/${docId}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Ingest failed with status ${response.status}`);
  }
  return await response.json();
}

export async function reindexDocument(docId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/v1/rag/reindex/${docId}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Re-index failed with status ${response.status}`);
  }
  return await response.json();
}

