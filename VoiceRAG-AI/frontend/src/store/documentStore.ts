import { create } from "zustand";
import type { DocumentInfoResponse } from "@/types/document";

interface DocumentStore {
  documents: DocumentInfoResponse[];
  selectedDocumentId: string | null;
  isLoading: boolean;
  error: string | null;

  setDocuments: (docs: DocumentInfoResponse[]) => void;
  addDocument: (doc: DocumentInfoResponse) => void;
  removeDocument: (document_id: string) => void;
  selectDocument: (document_id: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useDocumentStore = create<DocumentStore>((set) => ({
  documents: [],
  selectedDocumentId: null,
  isLoading: false,
  error: null,

  setDocuments: (docs) => set({ documents: docs, error: null }),

  addDocument: (doc) =>
    set((state) => ({
      documents: [
        doc,
        ...state.documents.filter((d) => d.document_id !== doc.document_id),
      ],
    })),

  removeDocument: (document_id) =>
    set((state) => ({
      documents: state.documents.filter((d) => d.document_id !== document_id),
      selectedDocumentId:
        state.selectedDocumentId === document_id
          ? null
          : state.selectedDocumentId,
    })),

  selectDocument: (document_id) =>
    set((state) => ({
      selectedDocumentId:
        state.selectedDocumentId === document_id ? null : document_id,
    })),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),
}));
