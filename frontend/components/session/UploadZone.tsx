"use client";

import { useAuthToken } from "@convex-dev/auth/react";
import { useQuery } from "convex/react";
import { useEffect, useRef, useState } from "react";
import { api } from "@/convex/_generated/api";
import { apiFetch, ApiError } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import type { Id } from "@/convex/_generated/dataModel";

const MAX_FILE_BYTES = 5 * 1024 * 1024;

export function UploadZone({ sessionId }: { sessionId: Id<"sessions"> }) {
  const token = useAuthToken();
  const documents = useQuery(api.documents.list, { sessionId });
  const { showToast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const seenReadyRef = useRef<Set<string> | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadingName, setUploadingName] = useState<string | null>(null);

  // Toast only for ready transitions that happen *after* the first snapshot
  // — not for already-ready documents on initial page load.
  useEffect(() => {
    if (documents === undefined) return;
    if (seenReadyRef.current === null) {
      seenReadyRef.current = new Set(
        documents.filter((d) => d.status === "ready").map((d) => d._id),
      );
      return;
    }
    for (const doc of documents) {
      if (doc.status === "ready" && !seenReadyRef.current.has(doc._id)) {
        seenReadyRef.current.add(doc._id);
        showToast(`${doc.fileName} ready · in scope`);
      }
    }
  }, [documents, showToast]);

  async function uploadFile(file: File) {
    setError(null);
    if (file.size > MAX_FILE_BYTES) {
      setError("This file is too large. Maximum size is 5MB per file.");
      return;
    }
    // Shown immediately, before the network upload even finishes — the
    // Convex "processing" row only exists once the request lands server
    // side, which left no feedback during the upload itself.
    setUploadingName(file.name);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", sessionId);
    try {
      await apiFetch("/ingest/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploadingName(null);
    }
  }

  async function handleCancel(documentId: string) {
    try {
      await apiFetch("/ingest/cancel", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ document_id: documentId }),
      });
    } catch {
      // Best-effort — the document's real status still arrives via Convex.
    }
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void uploadFile(file);
    event.target.value = "";
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) void uploadFile(file);
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={`flex flex-wrap items-center gap-2.5 border-b border-border px-7 py-[11px] ${
        isDragging ? "bg-secondary/40" : ""
      }`}
    >
      <span className="font-mono text-[10px] font-medium uppercase tracking-[.14em] text-muted-foreground/60">
        Materials
      </span>

      {documents === undefined
        ? null
        : documents
            .filter((d) => d.status !== "cancelled" && d.status !== "rejected")
            .map((doc) => (
              <div
                key={doc._id}
                className="flex items-center gap-2.5 border border-border bg-card px-[11px] py-[6px]"
              >
                <span className="font-mono text-xs text-foreground/90">{doc.fileName}</span>
                {doc.status === "ready" && (
                  <span className="font-mono text-[11px] text-muted-foreground/60">
                    · {doc.chunkCount} chunks
                  </span>
                )}
                {doc.status === "processing" && (
                  <>
                    <span className="inline-block h-[11px] w-[11px] animate-spin rounded-full border-[1.5px] border-border border-t-primary" />
                    <button
                      onClick={() => handleCancel(doc._id)}
                      className="font-mono text-xs text-muted-foreground/60 hover:text-destructive"
                    >
                      cancel
                    </button>
                  </>
                )}
                {doc.status === "failed" && (
                  <span className="font-mono text-[11px] text-destructive">
                    · {doc.error ?? "failed"}
                  </span>
                )}
              </div>
            ))}

      {/* FastAPI creates the Convex "processing" row before the upload
          POST's HTTP response even returns, so the real chip below can
          already be showing by the time this would render — without the
          guard, the same file briefly shows twice. */}
      {uploadingName && !(documents ?? []).some((d) => d.fileName === uploadingName) && (
        <div className="flex items-center gap-2.5 border border-border bg-card px-[11px] py-[6px]">
          <span className="inline-block h-[11px] w-[11px] animate-spin rounded-full border-[1.5px] border-border border-t-primary" />
          <span className="font-mono text-xs text-muted-foreground">
            Uploading {uploadingName}…
          </span>
        </div>
      )}

      <button
        onClick={() => inputRef.current?.click()}
        disabled={uploadingName !== null}
        className="border border-dashed border-border px-3 py-[6px] font-mono text-xs text-muted-foreground hover:border-primary hover:text-primary disabled:opacity-40"
      >
        + PDF
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={handleFileChange}
      />

      {error && <span className="font-mono text-xs text-destructive">{error}</span>}
    </div>
  );
}
