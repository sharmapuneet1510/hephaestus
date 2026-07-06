import type { HealthResponse } from "../api";
import { ForgeMark } from "./ForgeMark";

export type ConnState =
  | { kind: "connecting" }
  | { kind: "connected"; health: HealthResponse }
  | { kind: "error"; message: string };

export function Header({ conn, streaming }: { conn: ConnState; streaming: boolean }) {
  return (
    <header className="header">
      <div className="header__brand">
        <ForgeMark hot={streaming} />
        <span className="header__wordmark">
          HEPH<b>AES</b>TUS
        </span>
        <span className="header__tagline">forge · plan · test</span>
      </div>
      <div className="header__spacer" />
      <HealthPill conn={conn} />
    </header>
  );
}

function HealthPill({ conn }: { conn: ConnState }) {
  if (conn.kind === "connecting") {
    return (
      <div className="health health--pending" role="status">
        <span className="health__dot" />
        connecting…
      </div>
    );
  }
  if (conn.kind === "error") {
    return (
      <div className="health health--err" role="status" title={conn.message}>
        <span className="health__dot" />
        backend offline
      </div>
    );
  }
  const { health } = conn;
  return (
    <div className="health health--ok" role="status">
      <span className="health__dot" />
      backend v{health.version} · {health.ai_configured ? "AI ready" : "AI not configured"}
    </div>
  );
}
