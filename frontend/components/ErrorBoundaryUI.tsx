'use client';

import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, RefreshCcw, Home } from 'lucide-react';
import Link from 'next/link';

interface ErrorBoundaryUIProps {
  error: Error & { digest?: string };
  reset: () => void;
  context?: string;
}

export default function ErrorBoundaryUI({ error, reset, context = 'page' }: ErrorBoundaryUIProps) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error(`Error boundary caught an error in ${context}:`, error);
  }, [error, context]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] p-8 w-full font-sans">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="relative flex flex-col items-center max-w-lg w-full text-center p-10 rounded-3xl border border-white/5 bg-black/60 backdrop-blur-2xl shadow-2xl overflow-hidden"
      >
        <div className="absolute inset-0 bg-linear-to-br from-red-500/10 via-transparent to-orange-500/5 pointer-events-none" />
        
        <motion.div 
          initial={{ scale: 0.8, rotate: -10 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ type: "spring", bounce: 0.5, delay: 0.2 }}
          className="w-20 h-20 rounded-full bg-red-500/10 flex items-center justify-center mb-6 border border-red-500/20 shadow-[0_0_30px_rgba(239,68,68,0.2)]"
        >
          <AlertTriangle className="w-10 h-10 text-red-400" />
        </motion.div>

        <h2 className="text-3xl font-bold text-white mb-3 tracking-tight">
          System Interruption
        </h2>
        
        <p className="text-gray-400 mb-8 leading-relaxed text-sm">
          {error.message || `An unexpected anomaly occurred while loading this ${context}. Our monitoring systems have logged the event.`}
        </p>

        <div className="flex flex-col sm:flex-row gap-4 w-full justify-center relative z-10">
          <button
            onClick={() => reset()}
            className="group flex items-center justify-center gap-2 px-6 py-3 bg-white text-black font-semibold rounded-xl hover:bg-gray-200 transition-all duration-300 active:scale-95"
          >
            <RefreshCcw className="w-4 h-4 group-hover:rotate-180 transition-transform duration-500" />
            Attempt Recovery
          </button>
          
          <Link 
            href="/"
            className="flex items-center justify-center gap-2 px-6 py-3 bg-white/5 hover:bg-white/10 text-white font-semibold rounded-xl border border-white/10 transition-all duration-300 active:scale-95"
          >
            <Home className="w-4 h-4" />
            Return to Base
          </Link>
        </div>
        
        {error.digest && (
          <div className="mt-8 pt-4 border-t border-white/5 w-full">
            <p className="text-xs text-gray-500 font-mono">
              Error ID: {error.digest}
            </p>
          </div>
        )}
      </motion.div>
    </div>
  );
}
