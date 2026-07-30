"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface TypewriterTextProps {
  /** Array of words/phrases to cycle through */
  words: string[];
  /** Typing speed in ms per character */
  typingSpeed?: number;
  /** Deleting speed in ms per character */
  deletingSpeed?: number;
  /** Pause before deleting starts (ms) */
  pauseDuration?: number;
  /** CSS class for the text */
  className?: string;
}

/**
 * TypewriterText — Cycling typewriter effect for hero headlines.
 *
 * Types out words character by character, pauses, deletes, then types the
 * next word. Pure React state — no external dependency.
 * Blinking cursor via CSS animation.
 */
export default function TypewriterText({
  words,
  typingSpeed = 80,
  deletingSpeed = 50,
  pauseDuration = 2000,
  className = "",
}: TypewriterTextProps) {
  const [wordIndex, setWordIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isPaused, setIsPaused] = useState(false);

  const currentWord = words[wordIndex] || "";
  const displayText = currentWord.slice(0, charIndex);

  const tick = useCallback(() => {
    if (isPaused) return;

    if (!isDeleting) {
      // Typing forward
      if (charIndex < currentWord.length) {
        setCharIndex((c) => c + 1);
      } else {
        // Finished typing — pause before deleting
        setIsPaused(true);
        setTimeout(() => {
          setIsPaused(false);
          setIsDeleting(true);
        }, pauseDuration);
      }
    } else {
      // Deleting
      if (charIndex > 0) {
        setCharIndex((c) => c - 1);
      } else {
        // Finished deleting — move to next word
        setIsDeleting(false);
        setWordIndex((w) => (w + 1) % words.length);
      }
    }
  }, [charIndex, currentWord.length, isDeleting, isPaused, pauseDuration, wordIndex, words.length]);

  useEffect(() => {
    const speed = isDeleting ? deletingSpeed : typingSpeed;
    const timer = setTimeout(tick, isPaused ? pauseDuration : speed);
    return () => clearTimeout(timer);
  }, [tick, isDeleting, typingSpeed, deletingSpeed, isPaused, pauseDuration]);

  return (
    <span className={className}>
      <AnimatePresence mode="wait">
        <motion.span
          key={displayText}
          initial={{ opacity: 0.8 }}
          animate={{ opacity: 1 }}
          className="inline"
        >
          {displayText}
        </motion.span>
      </AnimatePresence>
      <span
        className="inline-block w-[3px] h-[1em] ml-1 align-middle rounded-full bg-current"
        style={{
          animation: "blink-cursor 1s steps(1) infinite",
        }}
      />
      <style jsx>{`
        @keyframes blink-cursor {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
      `}</style>
    </span>
  );
}
