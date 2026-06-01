import * as React from "react";

export type ActionTone = "activate" | "reset" | "send" | "dq" | "neutral";

const TONE_CLASSES: Record<ActionTone, string> = {
  activate: "border-[var(--tone-activate)] text-[var(--tone-activate)] hover:bg-[var(--tone-activate)]/10 hover:shadow-[0_0_10px_rgba(34,197,94,0.15)]",
  send: "border-[var(--tone-send)] text-[var(--tone-send)] hover:bg-[var(--tone-send)]/10 hover:shadow-[0_0_10px_rgba(59,130,246,0.15)]",
  reset: "border-[var(--tone-reset)] text-[var(--tone-reset)] hover:bg-[var(--tone-reset)]/10 hover:shadow-[0_0_10px_rgba(239,68,68,0.15)]",
  dq: "border-[var(--tone-dq)] text-[var(--tone-dq)] hover:bg-[var(--tone-dq)]/10 hover:shadow-[0_0_10px_rgba(220,38,38,0.15)]",
  neutral: "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--foreground)]/5 hover:text-[var(--foreground)]",
};

export interface ActionButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  tone: ActionTone;
  label: string;
  icon?: React.ReactNode;
}

export const ActionButton = React.forwardRef<HTMLButtonElement, ActionButtonProps>(
  ({ tone, label, icon, className, ...props }, ref) => (
    <button
      ref={ref}
      title={label}
      aria-label={label}
      className={`inline-flex h-7 w-7 items-center justify-center rounded-md border text-[11px] font-semibold transition-all duration-200 hover:scale-105 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed ${TONE_CLASSES[tone]} ${className || ''}`}
      {...props}
    >
      {icon || label[0]}
    </button>
  ),
);
ActionButton.displayName = "ActionButton";
