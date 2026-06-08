import { useState, useRef, useEffect } from "react";

const EXAMPLES = [
  "What dairy items expire this week?",
  "Which categories have low stock?",
  "What should I reorder today?",
  "Show me all expired items still in stock",
  "Which frozen items are running low?",
];

interface Message {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

export default function AskVikram() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (question: string) => {
    if (!question.trim() || streaming) return;

    const userMsg: Message = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);

    // Add an empty assistant message that we'll stream content into
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", streaming: true },
    ]);

    try {
      // Use native fetch for streaming — axios doesn't support ReadableStream natively.
      // We read the response body chunk-by-chunk and append each token to the message.
      const response = await fetch(
        `/api/inventory/ask?q=${encodeURIComponent(question)}`
      );

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decode the bytes chunk. { stream: true } tells the decoder that
        // more data may follow (handles multi-byte characters split across chunks).
        const chunk = decoder.decode(value, { stream: true });
        accumulated += chunk;

        // Update the last (assistant) message with accumulated text
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            role: "assistant",
            content: accumulated,
            streaming: true,
          };
          return updated;
        });
      }

      // Mark streaming as complete (removes the blinking cursor)
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          streaming: false,
        };
        return updated;
      });
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: "Sorry, I couldn't connect to the server. Is the backend running?",
          streaming: false,
        };
        return updated;
      });
    } finally {
      setStreaming(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <div className="flex flex-col h-screen max-h-screen p-8 gap-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Ask Vikram</h1>
        <p className="text-sm text-gray-500 mt-1">
          Ask anything about your inventory in plain English.
        </p>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto space-y-4 min-h-0">
        {messages.length === 0 && (
          <div className="space-y-4">
            <div className="card bg-accent-light border-blue-200">
              <p className="text-sm font-medium text-accent mb-3">Try asking Vikram:</p>
              <div className="space-y-2">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => sendMessage(ex)}
                    className="block w-full text-left text-sm px-3 py-2 rounded-lg
                               text-gray-700 hover:bg-white hover:text-accent transition-colors border border-transparent hover:border-blue-200"
                  >
                    → {ex}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center text-white text-xs font-bold shrink-0 mr-3 mt-1">
                V
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-accent text-white rounded-tr-sm"
                  : "bg-white border text-gray-800 rounded-tl-sm shadow-sm"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.streaming && (
                <span className="cursor-blink text-accent font-bold">▍</span>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={streaming}
          placeholder={streaming ? "Vikram is thinking…" : "Ask a warehouse question…"}
          className="flex-1 border rounded-xl px-4 py-3 text-sm focus:outline-none
                     focus:ring-2 focus:ring-accent/30 focus:border-accent disabled:bg-gray-50"
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          className="btn-primary rounded-xl px-5"
        >
          {streaming ? (
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" />
          ) : (
            "Send"
          )}
        </button>
      </form>
    </div>
  );
}
