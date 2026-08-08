export type DocumentStatus = "completed" | "failed" | "processing";

export interface DocumentUploadIngestResponse {
  document_id: string;
  filename: string;
  total_pages: number;
  total_chunks: number;
  status: string;
}

export interface DocumentInfoResponse {
  document_id: string;
  filename: string;
  total_chunks: number;
  total_pages?: number;
  status?: string;
}

export interface DocumentListApiResponse {
  documents: DocumentInfoResponse[];
  total: number;
}

export interface UploadFileEntry {
  file: File;
  id: string;
  progress: number;
  status: "pending" | "uploading" | "done" | "error";
  error?: string;
  result?: DocumentUploadIngestResponse;
}
