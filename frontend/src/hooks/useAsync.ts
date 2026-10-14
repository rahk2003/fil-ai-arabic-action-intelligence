import { useCallback, useEffect, useState } from "react";

export function useAsync<T>(loader: () => Promise<T>, immediate = true) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async () => {
    setLoading(true); setError(null);
    try { const value = await loader(); setData(value); return value; }
    catch (reason) { setError(reason instanceof Error ? reason.message : "حدث خطأ غير متوقع"); return null; }
    finally { setLoading(false); }
  }, [loader]);
  useEffect(() => { if (immediate) void run(); }, [immediate, run]);
  return { data, loading, error, run, setData };
}
