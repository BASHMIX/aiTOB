import { useState } from "react";
import axios from "axios";
import { useHubStore } from "@/store/useHubStore";

/**
 * Always-visible master switch for the auto-dispatcher.
 *
 * Two states:
 *   • OFF (default, gray pulse): every match is manually called by the TO.
 *   • ON  (amber, glowing):       per-tournament `auto_dispatch_enabled` settings take effect.
 *
 * Flipping OFF is the panic button — takes effect within ~20s (one dispatcher tick)
 * and leaves already-called matches running normally. Designed so the TO can
 * always reach this in one click from anywhere on the dashboard.
 */
export function DispatcherMasterSwitch() {
  const { status, setStatus } = useHubStore();
  const [busy, setBusy] = useState(false);
  const on = !!status.auto_dispatcher;

  const flip = async () => {
    if (busy) return;
    // Going ON warrants a confirm — going OFF is always fast & safe.
    if (!on && !confirm("Turn ON the auto-dispatcher? Bot will start calling matches automatically based on per-tournament settings.")) {
      return;
    }
    setBusy(true);
    try {
      await axios.post("/api/dispatcher/master", { enabled: !on });
      setStatus({ ...status, auto_dispatcher: !on });
    } catch (e: any) {
      alert(e.response?.data?.detail || e.message || "Failed to flip master switch");
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={flip}
      disabled={busy}
      title={on
        ? "Auto-dispatcher is ON — click to disable (instant stop, in-flight matches keep going)"
        : "Auto-dispatcher is OFF — click to enable. Per-tournament settings still required."}
      className={`shrink-0 flex items-center gap-2 px-3 py-1.5 rounded-md border text-xs font-bold tracking-wide transition-all disabled:opacity-50 ${
        on
          ? "bg-amber-500/20 border-amber-500/60 text-amber-200 hover:bg-amber-500/30 shadow-[0_0_12px_rgba(245,158,11,0.25)]"
          : "bg-black/30 border-white/15 text-textDim hover:border-amber-500/30 hover:text-amber-300"
      }`}
    >
      <span className={`relative flex h-2 w-2 ${on ? "" : ""}`}>
        {on && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-60"></span>
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${on ? "bg-amber-400" : "bg-gray-500"}`} />
      </span>
      <span>AUTO {on ? "ON" : "OFF"}</span>
    </button>
  );
}
