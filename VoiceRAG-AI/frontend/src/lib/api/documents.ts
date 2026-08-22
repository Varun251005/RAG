import type {
  DocumentInfoResponse,
  DocumentListApiResponse,
  DocumentUploadIngestResponse,
} from "@/types/document";
import apiClient from "./client";

const BASE = "/api/v1/documents";

/**
 * Upload a single PDF file to POST /api/v1/documents/upload with progress tracking.
 */
export async function uploadPdfDocument(
  file: File,
  onProgress?: (percent: number) => void
): Promise<DocumentUploadIngestResponse> {
  const form = new FormData();
  form.append("file", file);

  const response = await apiClient.post<DocumentUploadIngestResponse>(
    `${BASE}/upload`,
    form,
    {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      },
    }
  );

  return response.data;
}

/** Fetch list of all indexed documents from GET /api/v1/documents. */
export async function fetchDocuments(): Promise<DocumentListApiResponse> {
  const response = await apiClient.get<DocumentListApiResponse>(BASE);
  return response.data;
}

/** Fetch details for a specific document from GET /api/v1/documents/{documentId}. */
export async function fetchDocumentDetails(
  documentId: string
): Promise<DocumentInfoResponse> {
  const response = await apiClient.get<DocumentInfoResponse>(
    `${BASE}/${documentId}`
  );
  return response.data;
}

/** Get full absolute API URL for retrieving original PDF file binary. */
export function getDocumentFileUrl(documentId: string): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${baseUrl}${BASE}/${documentId}/file`;
}

/** Permanently delete document chunks from DELETE /api/v1/documents/{documentId}. */
export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`${BASE}/${documentId}`);
}

