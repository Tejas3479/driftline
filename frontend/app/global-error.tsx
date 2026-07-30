'use client';

import ErrorBoundaryUI from '@/components/ErrorBoundaryUI';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="bg-surface-0 text-slate-100 min-h-screen antialiased selection:bg-cyan-500 selection:text-slate-950">
        <ErrorBoundaryUI error={error} reset={reset} context="global root layout" />
      </body>
    </html>
  );
}
