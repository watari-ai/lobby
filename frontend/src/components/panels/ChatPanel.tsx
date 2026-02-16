import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useLobbyStore } from '../../stores/lobbyStore';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export function ChatPanel() {
  const { gatewayUrl } = useLobbyStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || !gatewayUrl || loading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${gatewayUrl.replace(/\/+$/, '')}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });

      if (!res.ok) {
        throw new Error(`${res.status} ${res.statusText}`);
      }

      const data = await res.json();
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: data.response ?? data.message ?? JSON.stringify(data),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `⚠️ Error: ${err.message}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  }, [input, gatewayUrl, loading]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!gatewayUrl) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        設定画面でGateway URLを設定してください。
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 text-sm">
        {messages.length === 0 && (
          <p className="text-muted-foreground text-xs">メッセージを入力して送信してください。</p>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={msg.role === 'user' ? 'text-right' : ''}>
            <span className="text-[10px] text-muted-foreground">
              {msg.role === 'user' ? 'You' : 'Assistant'}
            </span>
            <p className={`whitespace-pre-wrap break-words rounded px-2 py-1 inline-block max-w-full text-left ${
              msg.role === 'user'
                ? 'bg-primary/20 text-foreground'
                : 'bg-secondary text-secondary-foreground'
            }`}>
              {msg.content}
            </p>
          </div>
        ))}
        {loading && (
          <div className="text-muted-foreground text-xs animate-pulse">thinking...</div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border p-2 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="メッセージを入力..."
          className="flex-1 bg-secondary text-foreground text-sm rounded px-3 py-1.5 outline-none focus:ring-1 focus:ring-primary"
          disabled={loading}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          className="px-3 py-1.5 rounded text-sm bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          送信
        </button>
      </div>
    </div>
  );
}
