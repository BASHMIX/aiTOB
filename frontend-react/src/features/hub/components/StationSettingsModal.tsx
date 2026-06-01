import { useEffect, useState, useMemo } from "react";
import axios from "axios";
import { useHubStore } from "@/store/useHubStore";

interface Stream {
  id: string;
  name: string;
  source?: string | null;
  game?: string | null;
}

interface StationSettingsModalProps {
  station: any;
  onClose: () => void;
  onSaved: () => void;
}

// Derive a viewable Twitch/YouTube URL from a start.gg stream object.
// start.gg gives streamName (e.g. "fnctv") and streamSource (e.g. "TWITCH").
function deriveStreamUrl(stream: Stream | undefined): string {
  if (!stream) return "";
  const name = (stream.name || "").trim().replace(/^@/, "");
  if (!name) return "";
  switch ((stream.source || "").toUpperCase()) {
    case "TWITCH":  return `https://twitch.tv/${name}`;
    case "YOUTUBE": return `https://youtube.com/@${name}`;
    case "MIXER":   return `https://mixer.com/${name}`;
    default:        return "";
  }
}

export function StationSettingsModal({ station, onClose, onSaved }: StationSettingsModalProps) {
  const { currentSlug } = useHubStore();

  const [name, setName] = useState<string>(station.name || "");
  const [hidden, setHidden] = useState<boolean>(!!station.hidden);
  const [botEnabled, setBotEnabled] = useState<boolean>(station.bot_enabled !== false);
  const [streamId, setStreamId] = useState<string>(station.startgg_stream_id || "");
  const [streamUrlOverride, setStreamUrlOverride] = useState<string>(station.stream_url || "");
  const [activeOverlay, setActiveOverlay] = useState<string>(station.active_overlay || "");

  const [streams, setStreams] = useState<Stream[]>([]);
  const [overlays, setOverlays] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const reqs: Promise<any>[] = [axios.get("/api/overlays")];
        if (currentSlug) reqs.push(axios.get(`/api/tournaments/${currentSlug}/streams`));
        const [ovRes, strRes] = await Promise.all(reqs);
        if (cancelled) return;
        setOverlays((ovRes.data.overlays || []).map((o: any) => o.name).filter(Boolean));
        if (strRes) setStreams(strRes.data.streams || []);
      } catch (e) {
        console.error("StationSettingsModal load", e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [currentSlug]);

  const selectedStream = useMemo(
    () => streams.find(s => s.id === streamId),
    [streams, streamId]
  );
  const derivedUrl = deriveStreamUrl(selectedStream);

  const handleSave = async () => {
    setSaving(true);
    try {
      // Send only the fields that materially changed — exclude_unset on the
      // backend means we don't have to think about defaults.
      await axios.patch(`/api/stations/${station.id}`, {
        name: name.trim() || station.name,
        hidden,
        bot_enabled: botEnabled,
        startgg_stream_id: streamId || "",      // empty = unmap
        stream_url: streamUrlOverride || "",    // empty = use derived
        active_overlay: activeOverlay || "",    // empty = clear
      });
      onSaved();
      onClose();
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || "Save failed";
      alert(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div
        className="fixed left-1/2 top-1/2 z-50 w-[95%] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-white/10 bg-cardDark shadow-2xl flex flex-col max-h-[90%] overflow-hidden animate-fadeIn"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-white/10 px-5 py-4 flex items-center justify-between">
          <h2 className="text-base font-bold text-white tracking-wide">
            Station Settings – {station.name}
          </h2>
          <button onClick={onClose} className="text-textDim hover:text-white transition-colors">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="p-5 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
          {/* Name */}
          <label className="flex flex-col gap-1.5 p-3 rounded-lg bg-black/25 border border-white/5">
            <span className="text-sm font-semibold text-gray-200">Display Name</span>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              className="bg-black/40 border border-white/10 rounded px-2.5 py-1 text-sm text-white focus:outline-none focus:border-accentYellow/50"
            />
          </label>

          {/* start.gg stream */}
          <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-black/25 border border-white/5">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-gray-200">Start.gg Stream</span>
              {loading && <span className="text-xs text-textDim">loading…</span>}
            </div>
            <select
              value={streamId}
              onChange={e => setStreamId(e.target.value)}
              className="bg-black/40 border border-white/10 rounded px-2.5 py-1 text-sm text-white focus:outline-none focus:border-accentYellow/50"
              disabled={!currentSlug}
            >
              <option value="" className="text-black">Local only (no stream queue)</option>
              {streams.map(s => (
                <option key={s.id} value={s.id} className="text-black">
                  {s.name}{s.source ? ` (${s.source})` : ""}
                </option>
              ))}
            </select>
            <span className="text-xs text-textDim">
              {currentSlug
                ? "Matches assigned to this station will be pushed onto the start.gg public stream queue."
                : "Select a tournament first to see configured streams."}
            </span>
            {streams.length === 0 && currentSlug && !loading && (
              <span className="text-xs text-amber-400/80">
                No streams configured on this tournament. Add them in start.gg admin → Manage → Streams, then refresh the tournament.
              </span>
            )}
          </div>

          {/* Channel URL (auto/override) */}
          <label className="flex flex-col gap-1.5 p-3 rounded-lg bg-black/25 border border-white/5">
            <span className="text-sm font-semibold text-gray-200">Channel URL</span>
            <input
              type="text"
              value={streamUrlOverride}
              onChange={e => setStreamUrlOverride(e.target.value)}
              placeholder={derivedUrl || "https://twitch.tv/your-channel"}
              className="bg-black/40 border border-white/10 rounded px-2.5 py-1 text-sm text-white focus:outline-none focus:border-accentYellow/50 placeholder:text-textDim"
            />
            <span className="text-xs text-textDim">
              Leave blank to auto-derive from the start.gg stream. Override for Kick, restream pages, etc.
            </span>
          </label>

          {/* Active overlay */}
          <label className="flex flex-col gap-1.5 p-3 rounded-lg bg-black/25 border border-white/5">
            <span className="text-sm font-semibold text-gray-200">Active Overlay</span>
            <select
              value={activeOverlay}
              onChange={e => setActiveOverlay(e.target.value)}
              className="bg-black/40 border border-white/10 rounded px-2.5 py-1 text-sm text-white focus:outline-none focus:border-accentYellow/50"
            >
              <option value="" className="text-black">— None —</option>
              {overlays.map(o => (
                <option key={o} value={o} className="text-black">{o}</option>
              ))}
            </select>
          </label>

          {/* Bot enabled */}
          <label className="flex items-center justify-between p-3 rounded-lg bg-black/25 border border-white/5 cursor-pointer">
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold text-gray-200">Discord Bot Announces</span>
              <span className="text-xs text-textDim">Default for matches assigned to this station</span>
            </div>
            <input
              type="checkbox"
              checked={botEnabled}
              onChange={e => setBotEnabled(e.target.checked)}
              className="w-4 h-4 accent-accentYellow cursor-pointer rounded"
            />
          </label>

          {/* Hidden */}
          <label className="flex items-center justify-between p-3 rounded-lg bg-black/25 border border-white/5 cursor-pointer">
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold text-gray-200">Hide from Dashboard</span>
              <span className="text-xs text-textDim">Excluded from auto-assignment too</span>
            </div>
            <input
              type="checkbox"
              checked={hidden}
              onChange={e => setHidden(e.target.checked)}
              className="w-4 h-4 accent-accentYellow cursor-pointer rounded"
            />
          </label>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-white/10 px-5 py-3.5 bg-black/35 mt-auto">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-md text-sm font-semibold text-gray-400 hover:bg-white/5 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 rounded-md text-sm font-bold bg-accentYellow text-black hover:bg-yellow-400 transition-all disabled:opacity-50 disabled:pointer-events-none"
          >
            {saving ? "Saving…" : "Save Settings"}
          </button>
        </div>
      </div>
    </>
  );
}
