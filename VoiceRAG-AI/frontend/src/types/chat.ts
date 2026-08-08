export type MessageRole = "user" | "assistant" | "system";

export interface SourceCitation {
  chunk_id: string;
  snippet: string;
  page_number: number;
  original_filename: string;
  score: number;
  document_id: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  sources?: SourceCitation[];
  timestamp: string;
  isStreaming?: boolean;
  isError?: boolean;
  errorDetail?: string;
}

export interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  activeDocumentId: string | null;
  error: string | null;
  autoSpeak: boolean;
}

export interface ChatActions {
  sendMessage: (question: string) => Promise<void>;
  regenerateLastMessage: () => Promise<void>;
  clearChat: () => void;
  setActiveDocumentId: (documentId: string | null) => void;
  cancelStream: () => void;
  setAutoSpeak: (autoSpeak: boolean) => void;
}
