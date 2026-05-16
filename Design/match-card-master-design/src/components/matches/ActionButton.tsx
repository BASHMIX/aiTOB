import * as React from "react";
import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ActionTone = "activate" | "reset" | "send" | "dq" | "neutral";

const TONE_VARS: Record<ActionTone, React.CSSProperties> = {
  activate: {
    ["--action-border" as never]: "var(--tone-activate)",
    ["--action-text" as never]: "var(--tone-activate)",
  },
  send: {
    ["--action-border" as never]: "var(--tone-send)",
    ["--action-text" as never]: "var(--tone-send)",
  },
  reset: {
    ["--action-border" as never]: "var(--tone-reset)",
    ["--action-text" as never]: "var(--tone-reset)",
  },
  dq: {
    ["--action-border" as never]: "var(--tone-dq)",
    ["--action-text" as never]: "var(--tone-dq)",
  },
  neutral: {
    ["--action-border" as never]: "var(--border)",
    ["--action-text" as never]: "var(--muted-foreground)",
  },
};

export interface ActionButtonProps extends Omit<ButtonProps, "variant" | "size"> {
  tone: ActionTone;
  label: string;
}

export const ActionButton = React.forwardRef<HTMLButtonElement, ActionButtonProps>(
  ({ tone, label, style, className, ...props }, ref) => (
    <Button
      ref={ref}
      variant="action"
      size="action"
      style={{ ...TONE_VARS[tone], ...style }}
      className={cn(className)}
      {...props}
    >
      {label}
    </Button>
  ),
);
ActionButton.displayName = "ActionButton";
