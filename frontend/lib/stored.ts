"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * A small per-viewer setting (role, feed preferences), shared by every component that reads the
 * same key. The value lives in memory, so it always works; localStorage only remembers it across
 * visits (and other tabs), and when storage is unavailable (private windows, blocked site data)
 * the setting still changes, it just isn't remembered.
 */
export function useStored<T>(
  key: string,
  fallback: T,
  valid: (value: unknown) => value is T,
): [T, (value: T) => void] {
  const subscribe = useCallback(
    (notify: () => void) => {
      const keyListeners = listeners.get(key) ?? new Set();
      keyListeners.add(notify);
      listeners.set(key, keyListeners);
      // Another tab changed it.
      const onStorage = (e: StorageEvent) => {
        if (e.key !== key) return;
        memory.set(key, e.newValue);
        notify();
      };
      window.addEventListener("storage", onStorage);
      return () => {
        keyListeners.delete(notify);
        window.removeEventListener("storage", onStorage);
      };
    },
    [key],
  );
  const raw = useSyncExternalStore(
    subscribe,
    () => snapshot(key),
    () => null,
  );
  const set = useCallback(
    (next: T) => {
      const value = JSON.stringify(next);
      memory.set(key, value);
      try {
        window.localStorage.setItem(key, value);
      } catch {
        // Storage unavailable: the setting still applies for this visit.
      }
      for (const notify of listeners.get(key) ?? []) notify();
    },
    [key],
  );
  return [parse(raw, fallback, valid), set];
}

const memory = new Map<string, string | null>();
const listeners = new Map<string, Set<() => void>>();

function snapshot(key: string): string | null {
  if (!memory.has(key)) {
    let stored: string | null = null;
    try {
      stored = window.localStorage.getItem(key);
    } catch {
      // Storage unavailable: start from the fallback.
    }
    memory.set(key, stored);
  }
  return memory.get(key) ?? null;
}

function parse<T>(
  raw: string | null,
  fallback: T,
  valid: (value: unknown) => value is T,
): T {
  if (raw === null) return fallback;
  try {
    const value: unknown = JSON.parse(raw);
    return valid(value) ? value : fallback;
  } catch {
    return fallback;
  }
}
