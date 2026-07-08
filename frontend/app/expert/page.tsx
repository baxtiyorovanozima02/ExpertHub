"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRequireAuth } from "@/lib/hooks/use-require-auth";
import { useLogout } from "@/lib/hooks/use-auth";
import {
  fetchExpertDocuments,
  uploadTextDocument,
  uploadFileDocument,
  deleteDocument,
} from "@/lib/api/expert";
import { createConversation, sendMessage } from "@/lib/api/chat";
import { getApiErrorMessage } from "@/lib/api-client";
import type { ExpertDocument, ChatMessage } from "@/lib/types";

type Tab = "text" | "file" | "test";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("uz-UZ", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function ExpertPage() {
  const { isReady, user } = useRequireAuth({ allowedRoles: ["expert"] });
  const logout = useLogout();
  const queryClient = useQueryClient();

  const [tab, setTab] = useState<Tab>("text");
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [question, setQuestion] = useState("");
  const [replyWithAudio, setReplyWithAudio] = useState(false);
  const [testConversationId, setTestConversationId] = useState<number | null>(null);
  const [answer, setAnswer] = useState<ChatMessage | null>(null);

  const { data: documents = [], isLoading: docsLoading } = useQuery({
    queryKey: ["expert-documents"],
    queryFn: fetchExpertDocuments,
    enabled: isReady,
  });

  const textMutation = useMutation({
    mutationFn: () => uploadTextDocument({ content: text.trim(), source: source.trim() || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["expert-documents"] });
      setText("");
      setSource("");
      setError(null);
      setSuccess("Matn muvaffaqiyatli qo'shildi");
      setTimeout(() => setSuccess(null), 3000);
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  });

  const fileMutation = useMutation({
    mutationFn: () => uploadFileDocument(file!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["expert-documents"] });
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      setError(null);
      setSuccess("Fayl muvaffaqiyatli yuklandi");
      setTimeout(() => setSuccess(null), 3000);
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteDocument(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["expert-documents"] }),
    onError: (err) => setError(getApiErrorMessage(err)),
  });

  const askMutation = useMutation({
    mutationFn: async () => {
      let convId = testConversationId;
      if (!convId) {
        const conversation = await createConversation(null);
        convId = conversation.id;
        setTestConversationId(convId);
      }
      return sendMessage(convId, question.trim(), replyWithAudio);
    },
    onSuccess: (msg) => {
      setAnswer(msg);
      setQuestion("");
      setError(null);
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  });

  function handleAskSubmit() {
    if (!question.trim() || askMutation.isPending) return;
    setError(null);
    askMutation.mutate();
  }

  const isPending = textMutation.isPending || fileMutation.isPending;

  function handleTextSubmit() {
    if (!text.trim() || isPending) return;
    setError(null);
    textMutation.mutate();
  }

  function handleFileSubmit() {
    if (!file || isPending) return;
    setError(null);
    fileMutation.mutate();
  }

  if (!isReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-900 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
        <div>
          <p className="font-semibold text-gray-900">ExpertHub</p>
          <p className="text-xs text-gray-500">Ekspert paneli</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{user?.email}</span>
          <button
            onClick={logout}
            className="rounded-md border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
          >
            Chiqish
          </button>
        </div>
      </header>

      <div className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 md:px-6">
        {/* Upload section */}
        <div className="mb-8 rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h1 className="text-base font-semibold text-gray-900">Ma'lumot qo'shish</h1>
            <p className="mt-0.5 text-xs text-gray-500">
              Matn kiriting yoki fayl yuklang — bu ma'lumotlar AI javoblarida ishlatiladi
            </p>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-gray-200 px-6">
            {(["text", "file", "test"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setError(null); }}
                className={`-mb-px mr-4 border-b-2 py-3 text-sm font-medium transition-colors ${
                  tab === t
                    ? "border-gray-900 text-gray-900"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {t === "text" ? "Matn kiritish" : t === "file" ? "Fayl yuklash" : "Sinov (savol-javob)"}
              </button>
            ))}
          </div>

          <div className="px-6 py-5">
            {tab === "text" ? (
              <div className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    Manba (ixtiyoriy)
                  </label>
                  <input
                    type="text"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    placeholder="Masalan: Mehnat kodeksi, 2024"
                    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 outline-none placeholder:text-gray-400 focus:border-gray-400 focus:ring-2 focus:ring-gray-100"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    Matn <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    rows={8}
                    placeholder="Bilim bazasiga qo'shmoqchi bo'lgan ma'lumotni shu yerga yozing..."
                    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 outline-none placeholder:text-gray-400 focus:border-gray-400 focus:ring-2 focus:ring-gray-100 resize-none"
                  />
                  <p className="mt-1 text-xs text-gray-400">{text.length} belgi</p>
                </div>
                <button
                  onClick={handleTextSubmit}
                  disabled={!text.trim() || isPending}
                  className="rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
                >
                  {textMutation.isPending ? "Saqlanmoqda..." : "Saqlash"}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    Fayl tanlang <span className="text-red-500">*</span>
                  </label>
                  <div
                    onClick={() => fileRef.current?.click()}
                    className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 transition-colors ${
                      file
                        ? "border-gray-900 bg-gray-50"
                        : "border-gray-200 hover:border-gray-400 hover:bg-gray-50"
                    }`}
                  >
                    {file ? (
                      <>
                        <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-gray-900 text-white">
                          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                        <p className="text-sm font-medium text-gray-900">{file.name}</p>
                        <p className="mt-0.5 text-xs text-gray-500">
                          {(file.size / 1024).toFixed(1)} KB
                        </p>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setFile(null);
                            if (fileRef.current) fileRef.current.value = "";
                          }}
                          className="mt-2 text-xs text-red-500 hover:text-red-700"
                        >
                          Bekor qilish
                        </button>
                      </>
                    ) : (
                      <>
                        <svg className="mb-3 h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        <p className="text-sm font-medium text-gray-700">Fayl tanlash uchun bosing</p>
                        <p className="mt-1 text-xs text-gray-400">PDF, DOCX, TXT — 10 MB gacha</p>
                      </>
                    )}
                  </div>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".pdf,.docx,.txt,.doc"
                    className="hidden"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                </div>
                <button
                  onClick={handleFileSubmit}
                  disabled={!file || isPending}
                  className="rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
                >
                  {fileMutation.isPending ? "Yuklanmoqda..." : "Yuklash"}
                </button>
              </div>
            )}

            {tab === "test" && (
              <div className="space-y-4">
                <p className="text-xs text-gray-500">
                  Yuklagan hujjatlaringiz asosida savol berib sinab ko'ring. Javob
                  faqat hujjatlarda mavjud ma'lumotga asoslanadi.
                </p>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-gray-700">
                    Savolingiz <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    rows={3}
                    placeholder="Masalan: Hujjatingizda hayvonlar haqida qanday ma'lumot bor?"
                    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 outline-none placeholder:text-gray-400 focus:border-gray-400 focus:ring-2 focus:ring-gray-100 resize-none"
                  />
                </div>

                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={replyWithAudio}
                    onChange={(e) => setReplyWithAudio(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  Javobni audio (ovozli) shaklda ham olish
                </label>

                <button
                  onClick={handleAskSubmit}
                  disabled={!question.trim() || askMutation.isPending}
                  className="rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
                >
                  {askMutation.isPending ? "So'ralmoqda..." : "Savol berish"}
                </button>

                {answer && (
                  <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                    <p className="mb-1 text-xs font-medium text-gray-500">AI javobi</p>
                    <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-line">
                      {answer.content}
                    </p>

                    {answer.answer_audio_base64 && (
                      <audio
                        controls
                        className="mt-3 w-full"
                        src={`data:audio/ogg;base64,${answer.answer_audio_base64}`}
                      />
                    )}
                    {answer.answer_audio_error && (
                      <p className="mt-2 text-xs text-red-500">
                        Audio yaratilmadi: {answer.answer_audio_error}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {error && (
              <p className="mt-3 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-600">
                {error}
              </p>
            )}
            {success && (
              <p className="mt-3 rounded-lg border border-green-100 bg-green-50 px-3 py-2 text-sm text-green-700">
                {success}
              </p>
            )}
          </div>
        </div>

        {/* Documents list */}
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-base font-semibold text-gray-900">Hujjatlar</h2>
            <p className="mt-0.5 text-xs text-gray-500">
              Siz yuklagan barcha bilim materiallari
            </p>
          </div>

          {docsLoading ? (
            <div className="flex h-32 items-center justify-center">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-900 border-t-transparent" />
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
              <svg className="mb-3 h-10 w-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-sm font-medium text-gray-500">Hujjatlar yo'q</p>
              <p className="mt-1 text-xs text-gray-400">Birinchi materialni yuqoridan qo'shing</p>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {documents.map((doc: ExpertDocument) => (
                <DocumentRow
                  key={doc.id}
                  doc={doc}
                  onDelete={() => deleteMutation.mutate(doc.id)}
                  isDeleting={deleteMutation.isPending && deleteMutation.variables === doc.id}
                />
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function DocumentRow({
  doc,
  onDelete,
  isDeleting,
}: {
  doc: ExpertDocument;
  onDelete: () => void;
  isDeleting: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const preview = doc.content.slice(0, 120);
  const hasMore = doc.content.length > 120;

  return (
    <li className="px-6 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          {doc.source && (
            <p className="mb-1 text-xs font-medium text-gray-500">{doc.source}</p>
          )}
          <p className="text-sm text-gray-800 leading-relaxed">
            {expanded ? doc.content : preview}
            {hasMore && !expanded && "..."}
          </p>
          {hasMore && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-1 text-xs text-gray-400 hover:text-gray-700"
            >
              {expanded ? "Yig'ish" : "Ko'proq ko'rish"}
            </button>
          )}
          <p className="mt-2 text-xs text-gray-400">{formatDate(doc.created_at)}</p>
        </div>
        <button
          onClick={onDelete}
          disabled={isDeleting}
          className="shrink-0 rounded-md p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 disabled:opacity-50"
          title="O'chirish"
        >
          {isDeleting ? (
            <div className="h-4 w-4 animate-spin rounded-full border border-gray-400 border-t-transparent" />
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          )}
        </button>
      </div>
    </li>
  );
}