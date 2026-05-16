import * as React from "react";

export type ActionTone = "activate" | "reset" | "send" | "dq" | "neutral";

const TONE_CLASSES: Record<ActionTone, string> = {
  activate: "border-[var(--tone-activate)] text-[var(--tone-activate)] hover:bg-[var(--tone-activate)]/10",
  send: "border-[var(--tone-send)] text-[var(--tone-send)] hover:bg-[var(--tone-send)]/10",
  reset: "border-[var(--tone-reset)] text-[var(--tone-reset)] hover:bg-[var(--tone-reset)]/10",
  dq: "border-[var(--tone-dq)] text-[var(--tone-dq)] hover:bg-[var(--tone-dq)]/10",
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
      className={`inline-flex h-8 items-center justify-center gap-1.5 rounded-md border px-3 text-xs font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${TONE_CLASSES[tone]} ${className || ''}`}
      {...props}
    >
      {icon}
      {label}
    </button>
  ),
);
ActionButton.displayName = "ActionButton";
