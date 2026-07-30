"use client";

import React, { useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger);

type RevealType = "words" | "chars" | "lines";

interface TextRevealProps {
  children: string;
  /** Split and animate by words, characters, or lines */
  type?: RevealType;
  /** Stagger delay between each element */
  stagger?: number;
  /** Animation duration per element */
  duration?: number;
  /** HTML tag to render */
  as?: "h1" | "h2" | "h3" | "h4" | "p" | "span" | "div";
  /** Additional CSS classes */
  className?: string;
  /** Whether to trigger on scroll or on mount */
  triggerOnScroll?: boolean;
}

/**
 * TextReveal — Animated text reveal component.
 *
 * Splits text into words/chars/lines and animates each element
 * into view with a staggered fade-up effect. Each element is
 * wrapped in an overflow-hidden container for clean reveal.
 *
 * Uses GSAP for animation with automatic cleanup via useGSAP.
 */
export default function TextReveal({
  children,
  type = "words",
  stagger = 0.04,
  duration = 0.5,
  as: Tag = "div",
  className = "",
  triggerOnScroll = true,
}: TextRevealProps) {
  const containerRef = useRef<HTMLElement>(null);

  // Split text into elements
  const elements = React.useMemo(() => {
    if (type === "words") return children.split(/\s+/);
    if (type === "chars") return children.split("");
    // lines — treat each newline as a line
    return children.split("\n");
  }, [children, type]);

  useGSAP(
    () => {
      if (!containerRef.current) return;

      const prefersReducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
      ).matches;
      if (prefersReducedMotion) return;

      const spans = containerRef.current.querySelectorAll(".text-reveal-el");

      const animConfig: gsap.TweenVars = {
        opacity: 1,
        y: 0,
        duration,
        stagger,
        ease: "power3.out",
      };

      if (triggerOnScroll) {
        gsap.fromTo(
          spans,
          { opacity: 0, y: 20 },
          {
            ...animConfig,
            scrollTrigger: {
              trigger: containerRef.current,
              start: "top 85%",
              toggleActions: "play none none none",
            },
          }
        );
      } else {
        gsap.fromTo(
          spans,
          { opacity: 0, y: 20 },
          { ...animConfig, delay: 0.2 }
        );
      }
    },
    { scope: containerRef }
  );

  return (
    <Tag ref={containerRef as any} className={className}>
      {elements.map((el, i) => (
        <span
          key={`${el}-${i}`}
          className="inline-block overflow-hidden"
        >
          <span
            className="text-reveal-el inline-block opacity-0"
            style={{ willChange: "transform, opacity" }}
          >
            {el}
            {type === "words" && i < elements.length - 1 ? "\u00A0" : ""}
          </span>
        </span>
      ))}
    </Tag>
  );
}
