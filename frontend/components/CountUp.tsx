"use client";

import { useEffect, useState } from "react";
import { animate } from "framer-motion";

interface CountUpProps {
  from?: number;
  to: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
}

export default function CountUp({
  from = 0,
  to,
  duration = 0.8,
  decimals = 0,
  prefix = "",
  suffix = "",
  className = "",
}: CountUpProps) {
  const [displayVal, setDisplayVal] = useState<string>(
    `${prefix}${to.toFixed(decimals)}${suffix}`
  );

  useEffect(() => {
    const controls = animate(from, to, {
      duration,
      ease: "easeOut",
      onUpdate: (value) => {
        setDisplayVal(`${prefix}${value.toFixed(decimals)}${suffix}`);
      },
    });

    return () => controls.stop();
  }, [from, to, duration, decimals, prefix, suffix]);

  return <span className={className}>{displayVal}</span>;
}
