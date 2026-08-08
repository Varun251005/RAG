import { create } from "zustand";
import { v4 as uuidv4 } from "uuid";
import { ChatMessage, ChatState, ChatActions, SourceCitation } from "@/types/chat";
import { sendChatQuestion } from "@/lib/api/chat";

export const useChatStore = create<ChatState & ChatActions>((set, get) => ({
  messages: [],
  isStreaming: false,
  activeDocumentId: null,
  error: null,
  autoSpeak: false,

  setActiveDocumentId: (documentId: string | null) => {
    set({ activeDocumentId: documentId });
  },

  setAutoSpeak: (autoSpeak: boolean) => {
    set({ autoSpeak });
  },

  clearChat: () => {
    set({ messages: [], isStreaming: false, error: null });
  },

  cancelStream: () => {
    set((state) => {
      const messages = [...state.messages];
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
        messages[messages.length - 1] = {
          ...lastMsg,
          isStreaming: false,
        };
      }
      return { messages, isStreaming: false };
    });
  },

  sendMessage: async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || get().isStreaming) return;

    const userMessageId = uuidv4();
    const assistantMessageId = uuidv4();
    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    const userMessage: ChatMessage = {
      id: userMessageId,
      role: "user",
      content: trimmed,
      timestamp: now,
    };

    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      sources: [],
      timestamp: now,
      isStreaming: true,
    };

    set((state) => ({
      messages: [...state.messages, userMessage, assistantMessage],
      isStreaming: true,
      error: null,
    }));

    try {
      const res = await sendChatQuestion(trimmed, get().activeDocumentId);

      const sources: SourceCitation[] = (res.sources || []).map((s) => ({
        chunk_id: s.chunk_id,
        snippet: "",
        page_number: s.page_number,
        original_filename: s.filename,
        score: 1.0,
        document_id: s.document_id,
      }));

      set((state) => {
        const messages = [...state.messages];
        const idx = messages.findIndex((m) => m.id === assistantMessageId);
        if (idx !== -1) {
          messages[idx] = {
            ...messages[idx],
            content: res.answer || "No response generated.",
            sources,
            isStreaming: false,
          };
        }
        return { messages, isStreaming: false };
      });
    } catch (err: any) {
      const errorDetail =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        "Backend service unavailable. Please ensure server is running.";

      set((state) => {
        const messages = [...state.messages];
        const idx = messages.findIndex((m) => m.id === assistantMessageId);
        if (idx !== -1) {
          messages[idx] = {
            ...messages[idx],
            isStreaming: false,
            isError: true,
            errorDetail,
            content: "An error occurred while communicating with the VoiceRAG AI service.",
          };
        }
        return { messages, isStreaming: false, error: errorDetail };
      });
    }
  },

  regenerateLastMessage: async () => {
    const { messages, isStreaming } = get();
    if (isStreaming || messages.length === 0) return;

    let lastUserQuestion = "";
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        lastUserQuestion = messages[i].content;
        break;
      }
    }

    if (!lastUserQuestion) return;

    set((state) => {
      const updated = [...state.messages];
      if (updated.length > 0 && updated[updated.length - 1].role === "assistant") {
        updated.pop();
      }
      if (updated.length > 0 && updated[updated.length - 1].role === "user") {
        updated.pop();
      }
      return { messages: updated };
    });

    await get().sendMessage(lastUserQuestion);
  },
}));
