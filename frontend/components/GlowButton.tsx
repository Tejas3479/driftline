"use client";

import React, { useRef } from "react";
import { motion } from "framer-motion";

type Variant = "primary" | "secondary" | "ghost";
type Size = "sm" | "md" | "lg";

interface GlowButtonProps {
  children: React.ReactNode;
  variant?: Variant;
  size?: Size;
  /** Enable magnetic hover effect (button follows cursor slightly) */
  magnetic?: boolean;
  /** HTML button type */
  type?: "button" | "submit" | "reset";
  /** Click handler */
  onClick?: () => void;
  /** Link href — renders as <a> if provided */
  href?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

const sizeClasses: Record<Size, string> = {
  sm: "px-4 py-2 text-xs font-bold gap-1.5",
  md: "px-6 py-3 text-sm font-bold gap-2",
  lg: "px-8 py-4 text-base font-extrabold gap-2.5",
};

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-gradient-to-r from-cyan-500 via-indigo-500 to-violet-500 text-white shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40",
  secondary:
    "bg-transparent border border-slate-700 text-slate-200 hover:border-cyan-500/50 hover:text-white hover:shadow-glow-cyan-sm",
  ghost:
    "bg-transparent text-slate-400 hover:text-white hover:bg-slate-900/50",
};

/**
 * GlowButton — Premium animated button component.
 *
 * Features:
 * - Animated gradient background (primary variant)
 * - Glow shadow that intensifies on hover
 * - Spring-based press feedback (scale down)
 * - Optional magnetic hover (button follows cursor slightly)
 * - Shimmer sweep animation on hover
 * - Glass border effect (secondary variant)
 */
export default function GlowButton({
  children,
  variant = "primary",
  size = "md",
  magnetic = false,
  type = "button",
  onClick,
  href,
  disabled = false,
  className = "",
}: GlowButtonProps) {
  const buttonRef = useRef<HTMLElement>(null);

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!magnetic || !buttonRef.current || disabled) return;
    const rect = buttonRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const offsetX = (e.clientX - centerX) * 0.15;
    const offsetY = (e.clientY - centerY) * 0.15;
    buttonRef.current.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
  };

  const handleMouseLeave = () => {
    if (!magnetic || !buttonRef.current) return;
    buttonRef.current.style.transform = "translate(0px, 0px)";
  };

  const motionProps = {
    whileHover: disabled ? {} : { scale: 1.02 },
    whileTap: disabled ? {} : { scale: 0.97 },
    transition: { type: "spring" as const, stiffness: 400, damping: 25 },
  };

  const combinedClasses = `
    relative inline-flex items-center justify-center rounded-xl
    transition-all duration-300 overflow-hidden
    disabled:opacity-50 disabled:cursor-not-allowed
    focus-ring
    ${sizeClasses[size]}
    ${variantClasses[variant]}
    ${className}
  `.trim();

  const shimmerOverlay = variant === "primary" ? (
    <span
      aria-hidden="true"
      className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent transition-transform duration-700 group-hover:translate-x-full"
    />
  ) : null;

  if (href) {
    return (
      <motion.a
        ref={buttonRef as React.RefObject<HTMLAnchorElement>}
        href={href}
        className={`group ${combinedClasses}`}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        {...motionProps}
      >
        {shimmerOverlay}
        <span className="relative z-10 flex items-center gap-inherit">
          {children}
        </span>
      </motion.a>
    );
  }

  return (
    <motion.button
      ref={buttonRef as React.RefObject<HTMLButtonElement>}
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`group ${combinedClasses}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      {...motionProps}
    >
      {shimmerOverlay}
      <span className="relative z-10 flex items-center gap-inherit">
        {children}
      </span>
    </motion.button>
  );
}
