import { useRef, useState } from "react";

export function Composer({
  disabled,
  onSend,
}: {
  disabled: boolean;
  onSend: (text: string) => void;
}) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
    if (ref.current) ref.current.style.height = "auto";
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const autosize = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  };

  return (
    <div className="composer">
      <div className="composer__box">
        <textarea
          ref={ref}
          rows={1}
          value={value}
          placeholder="Ask Hephaestus to plan a change, explain code, or run tests…"
          aria-label="Message"
          onChange={(e) => {
            setValue(e.target.value);
            autosize(e.target);
          }}
          onKeyDown={onKeyDown}
        />
        <button
          className="send"
          type="button"
          onClick={submit}
          disabled={disabled || value.trim().length === 0}
          aria-label="Send message"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M4 12l15-7-7 15-2.5-5.5L4 12z"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinejoin="round"
              fill="currentColor"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
