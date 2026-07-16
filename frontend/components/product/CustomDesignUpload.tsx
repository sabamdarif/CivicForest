"use client";

// Custom-design upload on the product page. The browser does cosmetic-only checks
// (type + size + a preview) for fast feedback; the *authoritative* validation,
// content-sniff and re-encode all happen server-side (plan.md §8) — never trust these.
// Requires a selected variant and an authenticated session (the endpoint is auth-gated).

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError } from "@/lib/api/client";
import { createCustomDesign } from "@/lib/api/customDesigns";

// Cosmetic client caps — the server enforces the real limits regardless.
const MAX_BYTES = 15 * 1024 * 1024;
const ACCEPTED = ["image/png", "image/jpeg", "image/webp"];

export function CustomDesignUpload({
  variantId,
  selectionHint,
}: {
  variantId: string | null;
  selectionHint: string | null;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  function onPick(picked: File | null) {
    setError(null);
    setDone(false);
    if (!picked) {
      setFile(null);
      setPreview(null);
      return;
    }
    if (!ACCEPTED.includes(picked.type)) {
      setError("Please choose a PNG, JPG or WebP image.");
      return;
    }
    if (picked.size > MAX_BYTES) {
      setError("That file is over 15 MB. Please pick a smaller image.");
      return;
    }
    setFile(picked);
    setPreview(URL.createObjectURL(picked));
  }

  async function onSubmit() {
    if (!file || !variantId) return;
    setError(null);
    setSubmitting(true);
    try {
      await createCustomDesign({ design: file, variant_id: variantId });
      setDone(true);
      setFile(null);
      setPreview(null);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        router.push("/login");
        return;
      }
      setError(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="border-t border-black/10 pt-5">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between text-sm font-medium text-ink"
        aria-expanded={open}
      >
        <span>Add your own design (custom print)</span>
        <span className="text-ink/40">{open ? "−" : "+"}</span>
      </button>

      {open && (
        <div className="mt-4 space-y-3">
          {selectionHint ? (
            <p className="text-sm text-ink/50">{selectionHint}</p>
          ) : (
            <>
              <label className="block">
                <span className="sr-only">Choose a design image</span>
                <input
                  type="file"
                  accept={ACCEPTED.join(",")}
                  onChange={(e) => onPick(e.target.files?.[0] ?? null)}
                  className="block w-full text-sm text-ink/70 file:mr-4 file:rounded-sm file:border-0 file:bg-charcoal file:px-4 file:py-2 file:text-sm file:font-semibold file:uppercase file:tracking-wide file:text-cream hover:file:bg-charcoal-700"
                />
              </label>

              {preview && (
                <div className="relative h-32 w-32 overflow-hidden rounded-sm border border-black/10 bg-cream-dark">
                  <Image src={preview} alt="Design preview" fill sizes="128px" className="object-contain" />
                </div>
              )}

              <p className="text-xs text-ink/50">
                PNG, JPG or WebP up to 15 MB. Your design is reviewed before printing.
              </p>

              <button
                type="button"
                disabled={!file || submitting}
                onClick={onSubmit}
                className="btn-outline w-full justify-center disabled:opacity-40"
              >
                {submitting ? "Uploading…" : "Upload design"}
              </button>
            </>
          )}

          {done && (
            <p className="rounded-sm bg-green-50 px-3 py-2 text-sm text-green-700" role="status">
              Design uploaded. Add the item to your cart to order it — we&apos;ll review the
              artwork before printing.
            </p>
          )}
          {error && (
            <p className="rounded-sm bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
