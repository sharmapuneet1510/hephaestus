// Thin client for the Hephaestus backend API.

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  ai_configured: boolean;
  config: {
    server: { host: string; port: number };
    ai_configured: boolean;
    ai_endpoint_set: boolean;
    model_tiers: Record<string, string>;
    default_tier: string;
    ignore_paths: string[];
    context_max_tokens: number;
  };
}

/** Fetch backend health. Throws on network error or non-2xx response. */
export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const resp = await fetch("/api/health", { signal });
  if (!resp.ok) {
    throw new Error(`Backend returned ${resp.status}`);
  }
  return (await resp.json()) as HealthResponse;
}
