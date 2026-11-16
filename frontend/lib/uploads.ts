/**
 * The usage files the homeowner has chosen, kept in memory for this visit only.
 *
 * Files can't travel in the URL, so they live here while the homeowner moves between
 * steps (client-side navigation keeps this module alive). They are never written to
 * storage: closing or reloading the page forgets them, and the upload step asks again.
 */
import { useSyncExternalStore } from "react";

import type { UsageCheckResponse } from "./api-v2-types";

export interface UploadState {
  files: File[];
  check: UsageCheckResponse | null;   // the last check of exactly these files
}

const EMPTY: UploadState = { files: [], check: null };
let state: UploadState = EMPTY;
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

export function getUploads(): UploadState {
  return state;
}

/** Same file twice (same name, size and last-modified time) is only kept once. */
function key(f: File): string {
  return `${f.name}|${f.size}|${f.lastModified}`;
}

export function addFiles(added: File[]): void {
  const seen = new Set(state.files.map(key));
  const files = [...state.files, ...added.filter((f) => !seen.has(key(f)))];
  state = { files, check: null };
  emit();
}

export function removeFile(index: number): void {
  state = { files: state.files.filter((_, i) => i !== index), check: null };
  emit();
}

export function setCheck(files: File[], check: UsageCheckResponse): void {
  // Only keep a result that still matches the current files.
  if (files.length === state.files.length && files.every((f, i) => f === state.files[i])) {
    state = { ...state, check };
    emit();
  }
}

export function clearUploads(): void {
  state = EMPTY;
  emit();
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useUploads(): UploadState {
  return useSyncExternalStore(subscribe, getUploads, () => EMPTY);
}
