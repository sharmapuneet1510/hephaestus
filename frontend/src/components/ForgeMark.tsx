// The Hephaestus mark: a molten anvil that "heats up" (via CSS) while streaming.

export function ForgeMark({ hot = false }: { hot?: boolean }) {
  return (
    <svg
      className={`mark${hot ? " mark--hot" : ""}`}
      viewBox="0 0 32 32"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="ember" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffcf6b" />
          <stop offset="0.55" stopColor="#ff6a1a" />
          <stop offset="1" stopColor="#ff3d00" />
        </linearGradient>
      </defs>
      {/* Anvil silhouette */}
      <path
        d="M6 12 h20 l-3 5 h-6 v3 h4 v2 H7 v-2 h4 v-3 H9 c-3 0-5-2-5-4 h2 z"
        fill="url(#ember)"
      />
      {/* Spark */}
      <path d="M22 3 l1.6 3.4 L27 8 l-3.4 1.6 L22 13 l-1.6-3.4 L17 8 l3.4-1.6 z" fill="#ffcf6b" />
    </svg>
  );
}
