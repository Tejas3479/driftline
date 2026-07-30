"use client";

import { motion, AnimatePresence } from "framer-motion";
import { usePathname } from "next/navigation";

/**
 * PageTransition — Cinematic page transition wrapper.
 *
 * Upgraded from basic fade to spring physics + blur effect.
 * Uses AnimatePresence for proper exit animations.
 * Spring-based deceleration for natural feel (~0.5s perceived).
 */
export default function PageTransition({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={pathname}
        initial={{ opacity: 0, y: 12, filter: "blur(6px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
        exit={{ opacity: 0, y: -8, filter: "blur(4px)" }}
        transition={{
          type: "spring",
          stiffness: 260,
          damping: 25,
          mass: 0.8,
        }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
