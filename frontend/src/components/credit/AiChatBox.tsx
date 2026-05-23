"use client";
import { useEffect, useRef, useState } from "react";
import { Bot, Send, Sparkles } from "lucide-react";

import { creditApi, streamAiMessage, type AiMessage } from "@/lib/api/credit";

/** AI 对话框(详情页底部)。
 *
 * 初次进入显示已缓存的 ai_summary,然后用户可追问。每次追问走 SSE 流式接口
 * (POST /credit/ai/conversations/{id}/messages),逐 chunk 渲染。
 */
export function AiChatBox({
  companyId,
  aiSummary,
}: {
  companyId: number;
  aiSummary: string | null;
}) {
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AiMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 首次挂载创建会话
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const conv = await creditApi.createConversation(companyId);
        if (cancelled) return;
        setConversationId(conv.id);
        setMessages(conv.messages || []);
      } catch (e) {
        if (!cancelled) setError((e as Error).message || "无法创建会话");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  // 滚到底
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, streamingContent]);

  async function handleSend() {
    if (!conversationId || !input.trim() || streaming) return;
    const userText = input.trim();
    setInput("");
    setError(null);
    setStreaming(true);
    setStreamingContent("");

    // 本地先 push user 消息(乐观更新)
    const localUserMsg: AiMessage = {
      id: -Date.now(),
      role: "user",
      content: userText,
      sequence: messages.length + 1,
      created_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, localUserMsg]);

    let collected = "";
    await streamAiMessage(conversationId, userText, {
      onChunk: (chunk) => {
        collected += chunk;
        setStreamingContent(collected);
      },
      onError: (msg) => {
        setError(msg);
      },
      onDone: () => {
        if (collected) {
          setMessages((m) => [
            ...m,
            {
              id: -Date.now() - 1,
              role: "assistant",
              content: collected,
              sequence: m.length + 1,
              created_at: new Date().toISOString(),
            },
          ]);
        }
        setStreamingContent("");
        setStreaming(false);
      },
    });
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
        <Sparkles className="h-4 w-4 text-[#FF6B35]" />
        <h3 className="text-sm font-semibold text-slate-900">AI 综合评价</h3>
      </div>

      {/* 顶部:已缓存的 ai_summary */}
      <div className="border-b border-slate-100 px-4 py-3 text-sm leading-relaxed text-slate-700">
        {aiSummary ? (
          <div className="whitespace-pre-wrap">{aiSummary}</div>
        ) : (
          <div className="text-slate-400">
            AI 评价正在生成,或 LLM 暂不可用 — 可直接追问下方对话框。
          </div>
        )}
      </div>

      {/* 对话区 */}
      <div
        ref={scrollRef}
        className="max-h-80 overflow-y-auto px-4 py-3 space-y-3"
      >
        {messages.length === 0 && !streaming && (
          <div className="text-xs text-slate-400">还没有对话,试着问问"主要风险点是什么"。</div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={
              "flex gap-2 " + (m.role === "user" ? "justify-end" : "justify-start")
            }
          >
            {m.role === "assistant" && (
              <Bot className="mt-1 h-4 w-4 shrink-0 text-[#FF6B35]" />
            )}
            <div
              className={
                "max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm " +
                (m.role === "user"
                  ? "bg-[#003366] text-white"
                  : "bg-slate-50 text-slate-800")
              }
            >
              {m.content}
            </div>
          </div>
        ))}
        {streaming && (
          <div className="flex gap-2">
            <Bot className="mt-1 h-4 w-4 shrink-0 text-[#FF6B35] animate-pulse" />
            <div className="max-w-[80%] whitespace-pre-wrap rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-800">
              {streamingContent || <span className="text-slate-400">思考中…</span>}
            </div>
          </div>
        )}
        {error && (
          <div className="text-xs text-red-500">⚠️ {error}</div>
        )}
      </div>

      {/* 输入区 */}
      <div className="flex items-center gap-2 border-t border-slate-100 px-3 py-2.5">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={!conversationId || streaming}
          placeholder={
            conversationId
              ? "针对该企业追问任何问题…"
              : "正在准备会话…"
          }
          className="flex-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm focus:border-[#003366] focus:outline-none disabled:bg-slate-50"
        />
        <button
          onClick={handleSend}
          disabled={!conversationId || streaming || !input.trim()}
          className="rounded-md bg-[#003366] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#002244] disabled:bg-slate-300"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
