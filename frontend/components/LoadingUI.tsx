'use client';

import { motion } from 'framer-motion';
import { Activity } from 'lucide-react';

export default function LoadingUI({ text = 'Initializing...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] w-full font-sans">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="flex flex-col items-center justify-center gap-6"
      >
        <div className="relative flex items-center justify-center">
          {/* Outer glow ring */}
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 4, ease: "linear" }}
            className="absolute w-28 h-28 rounded-full border border-dashed border-cyan-500/20"
          />
          
          {/* Inner pulse ring */}
          <motion.div
            animate={{ scale: [1, 1.25, 1], opacity: [0.3, 0.6, 0.3] }}
            transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
            className="absolute w-16 h-16 rounded-full bg-cyan-500/20 blur-xl"
          />
          
          {/* Center icon container */}
          <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-950 border border-slate-800 shadow-[0_0_30px_rgba(34,211,238,0.15)] z-10 overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-tr from-cyan-500/10 to-purple-500/10" />
            <Activity className="h-6 w-6 text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
          </div>
        </div>
        
        <div className="flex flex-col items-center gap-2.5">
          <motion.h3 
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
            className="text-xs font-extrabold tracking-[0.25em] text-cyan-400 uppercase"
          >
            {text}
          </motion.h3>
          
          <div className="flex gap-2">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                animate={{ 
                  y: [0, -6, 0],
                  scale: [1, 1.2, 1],
                  opacity: [0.3, 1, 0.3]
                }}
                transition={{
                  repeat: Infinity,
                  duration: 1,
                  delay: i * 0.15,
                  ease: "easeInOut",
                }}
                className="w-1.5 h-1.5 rounded-full bg-cyan-500"
              />
            ))}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
