"use client";

import { useCallback } from "react";

interface HapticsAPI {
  /** Light tap — 10ms vibration */
  tap: () => void;
  /** Standard click — 25ms vibration */
  click: () => void;
  /** Double pulse — success pattern */
  success: () => void;
  /** Long buzz — error/warning */
  error: () => void;
}

/**
 * useHaptics — Mobile vibration feedback hook.
 *
 * Provides haptic feedback patterns for different interaction types.
 * No-op on desktop or unsupported browsers.
 * Respects prefers-reduced-motion (all patterns become no-ops).
 */
export function useHaptics(): HapticsAPI {
  const vibrate = useCallback((pattern: number | number[]) => {
    if (typeof navigator === "undefined") return;
    if (!("vibrate" in navigator)) return;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReducedMotion) return;

    try {
      navigator.vibrate(pattern);
    } catch {
      // Silently fail
    }
  }, []);

  return {
    tap: useCallback(() => vibrate(10), [vibrate]),
    click: useCallback(() => vibrate(25), [vibrate]),
    success: useCallback(() => vibrate([15, 50, 15]), [vibrate]),
    error: useCallback(() => vibrate(100), [vibrate]),
  };
}
