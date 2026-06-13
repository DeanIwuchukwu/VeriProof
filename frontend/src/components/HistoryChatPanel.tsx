import { useMemo, useState } from "react";
import { historyChat } from "../api";
import type {
  HistoryChatCitation,
  HistoryChatTurn,
  HistoryItem,
} from "../types";

type ChatMessage =
  | { role: "assistant"; content: string; citations?: HistoryChatCitation[]; pdfUsed?: boolean }
  | { role: "user"; content: string };

export function HistoryChatPanel({
  items,
  openVerificationId,
}: {
  items: HistoryItem[];
  openVerificationId: string | null;
}) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "Ask about saved verifications, reviewer decisions, or what a shortlisted PDF says.",
    },
  ]);

  const recentTurns = useMemo<HistoryChatTurn[]>(
    () =>
      messages
        .filter((m) => m.content.trim())
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content })),
    [messages],
  );

  async function send() {
    const message = draft.trim();
    if (!message || busy) return;
    setBusy(true);
    setError(null);
    setDraft("");
    setMessages((list) => [...list, { role: "user", content: message }]);
    try {
      const res = await historyChat({
        message,
        open_verification_id: openVerificationId,
        visible_items: items,
        recent_turns: recentTurns,
      });
      setMessages((list) => [
        ...list,
        {
          role: "assistant",
          content: res.answer,
          citations: res.citations,
          pdfUsed: res.pdf_used,
        },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The history assistant could not answer.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="history-chat">
      <div className="history-chat-head">
        <span className="history-chat-title">History Assistant</span>
        <span className="history-chat-sub">
          {items.length
            ? openVerificationId
              ? "Using the saved history and the opened record."
              : "Using the saved history list."
            : "No saved history loaded yet."}
        </span>
      </div>

      <div className="history-chat-log" role="log" aria-live="polite">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`history-chat-bubble ${msg.role === "user" ? "user" : "assistant"}`}
          >
            <div className="history-chat-role">{msg.role === "user" ? "You" : "Assistant"}</div>
            <div className="history-chat-text">{msg.content}</div>
            {"citations" in msg && msg.citations && msg.citations.length > 0 && (
              <div className="history-chat-cites">
                <span className="history-chat-cites-label">
                  {msg.pdfUsed ? "Used history + PDF context:" : "Used history context:"}
                </span>
                {msg.citations.map((cite, citeIdx) => (
                  <span key={`${cite.verification_id}-${citeIdx}`} className="history-chat-cite">
                    {cite.filename ?? cite.ttb_id ?? cite.verification_id}
                    {cite.page ? ` p.${cite.page}` : ""}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && (
          <div className="history-chat-bubble assistant">
            <div className="history-chat-role">Assistant</div>
            <div className="history-chat-text">Searching saved history…</div>
          </div>
        )}
      </div>

      {error && (
        <div className="history-chat-error" role="alert">
          {error}
        </div>
      )}

      <div className="history-chat-input">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={
            items.length
              ? "Ask me about any of the records"
              : "Saved history will appear here after you verify a record."
          }
          disabled={busy || items.length === 0}
          rows={4}
        />
        <button className="btn-primary" onClick={() => void send()} disabled={!draft.trim() || busy || items.length === 0}>
          {busy ? "Thinking…" : "Submit"}
        </button>
      </div>
    </div>
  );
}
