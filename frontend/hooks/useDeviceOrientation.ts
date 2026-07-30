"use client";

import { useEffect, useRef, useState } from "react";

interface DeviceOrientation {
  /** Tilt front-to-back, normalized to [-1, 1] */
  beta: number;
  /** Tilt left-to-right, normalized to [-1, 1] */
  gamma: number;
}

/**
 * useDeviceOrientation — Mobile gyroscope tilt hook.
 *
 * Returns normalized beta/gamma values for parallax effects.
 * Handles iOS permission request. Returns null on desktop
 * or when prefers-reduced-motion is set.
 */
export function useDeviceOrientation(): DeviceOrientation | null {
  const [orientation, setOrientation] = useState<DeviceOrientation | null>(null);
  const permissionRequested = useRef(false);

  useEffect(() => {
    // Only run on devices with the API
    if (typeof window === "undefined" || !("DeviceOrientationEvent" in window)) {
      return;
    }

    // Disable for reduced motion
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReducedMotion) return;

    // Check if this is a touch device (proxy for mobile)
    const isTouchDevice =
      "ontouchstart" in window || navigator.maxTouchPoints > 0;
    if (!isTouchDevice) return;

    const handleOrientation = (e: DeviceOrientationEvent) => {
      const beta = e.beta != null ? Math.max(-45, Math.min(45, e.beta)) / 45 : 0;
      const gamma = e.gamma != null ? Math.max(-45, Math.min(45, e.gamma)) / 45 : 0;
      setOrientation({ beta, gamma });
    };

    // iOS 13+ requires permission request
    const requestPermission = async () => {
      if (permissionRequested.current) return;
      permissionRequested.current = true;

      const DOE = DeviceOrientationEvent as any;
      if (typeof DOE.requestPermission === "function") {
        try {
          const permission = await DOE.requestPermission();
          if (permission === "granted") {
            window.addEventListener("deviceorientation", handleOrientation);
          }
        } catch {
          // Permission denied or error
        }
      } else {
        // Non-iOS — just listen
        window.addEventListener("deviceorientation", handleOrientation);
      }
    };

    requestPermission();

    return () => {
      window.removeEventListener("deviceorientation", handleOrientation);
    };
  }, []);

  return orientation;
}
