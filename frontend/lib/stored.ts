"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * A small value kept in localStorage and shared by every component that reads the same key (and
 * by other tabs). It is a per-viewer convenience: if storage is unavailable (private windows,
 * blocked site data) the page still works with the fallback, it just doesn't remember.
 */
export function useStored<T>(
  key: string,
  fallback: T,
  valid: (value: unknown) => value is T,
): [T, (value: T) => void] {
  const subscribe = useCallback(
    (notify: () => void) => {
      const onStorage = (e: StorageEvent | CustomEvent<string>) => {
        const changed = e instanceof StorageEvent ? e.key : e.detail;
        if (changed === key) notify();
      };
      window.addEventListener("storage", onStorage);
      window.addEventListener(LOCAL_EVENT, onStorage as EventListener);
      return () => {
        window.removeEventListener("storage", onStorage);
        window.removeEventListener(LOCAL_EVENT, onStorage as EventListener);
      };
    },
    [key],
  );
  const raw = useSyncExternalStore(
    subscribe,
    () => read(key),
    () => null,
  );
  const value = parse(raw, fallback, valid);
  const set = useCallback(
    (next: T) => {
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // Storage unavailable: nothing to remember it in.
      }
      window.dispatchEvent(new CustomEvent(LOCAL_EVENT, { detail: key }));
    },
    [key],
  );
  return [value, set];
}

const LOCAL_EVENT = "matchdesk:stored";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
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
