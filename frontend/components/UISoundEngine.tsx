"use client";

import React, { createContext, useContext, useCallback, useRef, useState, useEffect } from "react";

type SoundType = "hover" | "click" | "success" | "error" | "whoosh";

interface UISoundContextValue {
  playSound: (type: SoundType) => void;
  isMuted: boolean;
  toggleMute: () => void;
}

const UISoundContext = createContext<UISoundContextValue>({
  playSound: () => {},
  isMuted: true,
  toggleMute: () => {},
});

export function useUISound() {
  return useContext(UISoundContext);
}

/**
 * UISoundProvider — Procedural audio feedback system.
 *
 * Uses the Web Audio API for synthesized micro-sounds.
 * All sounds are procedurally generated — zero audio files loaded.
 *
 * Initializes AudioContext on first user interaction.
 * Global mute toggle persisted in localStorage.
 * Disabled when prefers-reduced-motion is set.
 */
export function UISoundProvider({ children }: { children: React.ReactNode }) {
  const [isMuted, setIsMuted] = useState(true);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const initializedRef = useRef(false);

  // Load mute preference from localStorage
  useEffect(() => {
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReducedMotion) {
      setIsMuted(true);
      return;
    }

    const stored = localStorage.getItem("driftline-ui-sounds");
    setIsMuted(stored !== "enabled");
  }, []);

  const getAudioContext = useCallback(() => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioContext();
    }
    if (audioCtxRef.current.state === "suspended") {
      audioCtxRef.current.resume();
    }
    return audioCtxRef.current;
  }, []);

  const playSound = useCallback(
    (type: SoundType) => {
      if (isMuted) return;

      try {
        const ctx = getAudioContext();
        const now = ctx.currentTime;

        switch (type) {
          case "hover": {
            // Gentle high-pitched tick
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(1200, now);
            gain.gain.setValueAtTime(0.03, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
            osc.connect(gain).connect(ctx.destination);
            osc.start(now);
            osc.stop(now + 0.08);
            break;
          }
          case "click": {
            // Soft percussive tap
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "triangle";
            osc.frequency.setValueAtTime(800, now);
            osc.frequency.exponentialRampToValueAtTime(300, now + 0.05);
            gain.gain.setValueAtTime(0.06, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
            osc.connect(gain).connect(ctx.destination);
            osc.start(now);
            osc.stop(now + 0.1);
            break;
          }
          case "success": {
            // Ascending two-note chime (C5 → E5)
            const osc1 = ctx.createOscillator();
            const osc2 = ctx.createOscillator();
            const gain = ctx.createGain();
            osc1.type = "sine";
            osc1.frequency.setValueAtTime(523.25, now); // C5
            osc2.type = "sine";
            osc2.frequency.setValueAtTime(659.25, now); // E5
            gain.gain.setValueAtTime(0.04, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
            osc1.connect(gain).connect(ctx.destination);
            osc2.connect(gain);
            osc1.start(now);
            osc1.stop(now + 0.15);
            osc2.start(now + 0.12);
            osc2.stop(now + 0.3);
            break;
          }
          case "error": {
            // Descending low tone
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(400, now);
            osc.frequency.exponentialRampToValueAtTime(200, now + 0.15);
            gain.gain.setValueAtTime(0.05, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
            osc.connect(gain).connect(ctx.destination);
            osc.start(now);
            osc.stop(now + 0.2);
            break;
          }
          case "whoosh": {
            // Filtered noise sweep
            const bufferSize = ctx.sampleRate * 0.2;
            const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
            const data = buffer.getChannelData(0);
            for (let i = 0; i < bufferSize; i++) {
              data[i] = (Math.random() * 2 - 1) * 0.5;
            }
            const noise = ctx.createBufferSource();
            noise.buffer = buffer;
            const filter = ctx.createBiquadFilter();
            filter.type = "bandpass";
            filter.frequency.setValueAtTime(2000, now);
            filter.frequency.exponentialRampToValueAtTime(500, now + 0.2);
            filter.Q.setValueAtTime(1, now);
            const gain = ctx.createGain();
            gain.gain.setValueAtTime(0.04, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
            noise.connect(filter).connect(gain).connect(ctx.destination);
            noise.start(now);
            noise.stop(now + 0.2);
            break;
          }
        }
      } catch {
        // Silently fail — audio is a nice-to-have
      }
    },
    [isMuted, getAudioContext]
  );

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      localStorage.setItem("driftline-ui-sounds", next ? "disabled" : "enabled");
      // Initialize audio context on first unmute
      if (!next && !initializedRef.current) {
        getAudioContext();
        initializedRef.current = true;
      }
      return next;
    });
  }, [getAudioContext]);

  return (
    <UISoundContext.Provider value={{ playSound, isMuted, toggleMute }}>
      {children}
    </UISoundContext.Provider>
  );
}
