import useSWR, { SWRConfiguration, SWRResponse } from 'swr';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const fetcher = async (url: string) => {
  const fullUrl = url.startsWith('/') ? `${API_BASE_URL}${url}` : url;
  const headers = new Headers();
  const res = await fetch(fullUrl, {
    headers,
    credentials: "include",
  });
  
  if (res.status === 401 && typeof window !== 'undefined') {
    if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
      window.location.href = '/login';
    }
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        detail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {}
    const error = new Error(`API Error: ${detail}`);
    throw error;
  }
  
  return res.json();
};

export function useApi<Data = any, Error = any>(
  url: string | null,
  options?: SWRConfiguration<Data, Error>
): SWRResponse<Data, Error> {
  return useSWR<Data, Error>(url, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 5000,
    ...options,
  });
}
