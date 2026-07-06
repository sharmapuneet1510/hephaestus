import { useEffect, useState } from "react";
import { fetchHealth, type HealthResponse } from "./api";

type ConnState =
  | { kind: "connecting" }
  | { kind: "connected"; health: HealthResponse }
  | { kind: "error"; message: string };

/**
 * Hephaestus startup screen (SUBTASK 1.4). Confirms the backend connection on
 * load by polling /api/health, and shows a clear status while connecting or on
 * failure. The full three-panel workspace UI arrives in TASK 2.
 */
export function App() {
  const [state, setState] = useState<ConnState>({ kind: "connecting" });

  useEffect(() => {
    const controller = new AbortController();

    async function check() {
      try {
        const health = await fetchHealth(controller.signal);
        setState({ kind: "connected", health });
      } catch (err) {
        if (controller.signal.aborted) return;
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : "Unknown error",
        });
      }
    }

    check();
    return () => controller.abort();
  }, []);

  return (
    <div className="startup">
      <div className="startup__card">
        <h1 className="startup__title">🔨 Hephaestus</h1>
        <p className="startup__tagline">
          Forge better software with agentic code intelligence.
        </p>
        <StatusBadge state={state} />
      </div>
    </div>
  );
}

function StatusBadge({ state }: { state: ConnState }) {
  if (state.kind === "connecting") {
    return <div className="status status--pending">Connecting to backend…</div>;
  }
  if (state.kind === "error") {
    return (
      <div className="status status--error">
        <strong>Backend unavailable.</strong> {state.message}
        <div className="status__hint">
          Start it with: <code>cd backend &amp;&amp; uvicorn app.main:app --reload</code>
        </div>
      </div>
    );
  }

  const { health } = state;
  return (
    <div className="status status--ok">
      <strong>Backend connected ✓</strong>
      <ul className="status__meta">
        <li>Service: {health.service} v{health.version}</li>
        <li>
          AI: {health.ai_configured ? "configured" : "not configured (set env vars)"}
        </li>
        <li>Default model tier: {health.config.default_tier}</li>
      </ul>
    </div>
  );
}
