"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Two-step confirmation: read what will happen, then type the exact word. The confirm button stays
 * disabled until the typed text matches, and the server checks the word again.
 */
export function ConfirmDialog({
  title,
  word,
  tone,
  points,
  onConfirm,
  onCancel,
}: {
  title: string;
  word: string;
  tone: "warning" | "danger";
  points: string[];
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [step, setStep] = useState<1 | 2>(1);
  const [typed, setTyped] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const danger = tone === "danger";

  const first = useRef<HTMLButtonElement>(null);
  const opener = useRef<Element | null>(null);

  // Escape cancels; focus moves into the dialog and returns to the element that opened it.
  useEffect(() => {
    opener.current = document.activeElement;
    first.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (opener.current instanceof HTMLElement) opener.current.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once per dialog; onCancel is read at call time
  }, []);

  useEffect(() => {
    if (step === 2) input.current?.focus();
  }, [step]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="presentation">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className={`w-full max-w-lg rounded-xl border-2 bg-white p-5 shadow-xl dark:bg-slate-900 ${
          danger ? "border-red-600" : "border-amber-500"
        }`}
      >
        <h2 id="confirm-title" className={`text-lg font-semibold ${danger ? "text-red-700 dark:text-red-300" : ""}`}>
          {title}
        </h2>
        {step === 1 ? (
          <>
            <p className="mt-2 text-sm text-slate-500">Bước 1/2 — đọc kỹ điều sẽ xảy ra:</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
            <div className="mt-4 flex justify-end gap-2">
              <button ref={first} type="button" onClick={onCancel} className="rounded-md border border-slate-400 px-3 py-1 text-sm">
                Hủy
              </button>
              <button
                type="button"
                onClick={() => setStep(2)}
                className="rounded-md border border-slate-500 bg-slate-800 px-3 py-1 text-sm text-white dark:bg-slate-200 dark:text-slate-900"
              >
                Tiếp tục
              </button>
            </div>
          </>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (typed === word) onConfirm();
            }}
          >
            <label htmlFor="confirm-word" className="mt-2 block text-sm">
              Bước 2/2 — gõ chính xác <strong className="font-mono">{word}</strong> để xác nhận:
            </label>
            <input
              id="confirm-word"
              ref={input}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              className="mt-2 w-full rounded-md border border-slate-400 bg-transparent px-2 py-1 font-mono"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={onCancel} className="rounded-md border border-slate-400 px-3 py-1 text-sm">
                Hủy
              </button>
              <button
                type="submit"
                disabled={typed !== word}
                className={`rounded-md px-3 py-1 text-sm font-semibold text-white disabled:opacity-40 ${
                  danger ? "bg-red-600" : "bg-amber-600"
                }`}
              >
                Xác nhận {word}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
