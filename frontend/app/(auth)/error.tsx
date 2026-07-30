'use client';

import ErrorBoundaryUI from '@/components/ErrorBoundaryUI';

export default function AuthError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorBoundaryUI error={error} reset={reset} context="authentication area" />;
}
