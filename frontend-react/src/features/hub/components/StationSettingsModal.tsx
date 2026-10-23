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
  const { currentSlug, events, streamGate, setStreamGate, tournaments } = useHubStore();
  const isStartGgTournament = tournaments.find((tournament) => tournament.slug === currentSlug)?.provider_type !== 'challonge';

  const [name, setName] = useState<string>(station.name || "");
  const [hidden, setHidden] = useState<boolean>(!!station.hidden);
  const [botEnabled, setBotEnabled] = useState<boolean>(station.bot_enabled !== false);
  const [streamId, setStreamId] = useState<string>(station.startgg_stream_id || "");
  const [streamUrlOverride, setStreamUrlOverride] = useState<string>(station.stream_url || "");
  const [activeOverlay, setActiveOverlay] = useState<string>(station.active_overlay || "");
  // Green-room: event-binding + broadcaster lobby credentials (commit #7)
  const [eventId, setEventId] = useState<string>(station.event_id || "");
  const [isStreamStation, setIsStreamStation] = useState<boolean>(!!station.is_stream_station);
  const [roomNameOrId, setRoomNameOrId] = useState<string>(station.room_name_or_id || "");
  const [roomPassword, setRoomPassword] = useState<string>(station.room_password || "");

  const [streams, setStreams] = useState<Stream[]>([]);
  const [overlays, setOverlays] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [binding, setBinding] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedToken, setCopiedToken] = useState(false);

  const handleCopyStationLink = async (onlyToken = false) => {
    try {
      const res = await axios.post(`/api/stations/${station.id}/overlay-access`);
      const url = `${window.location.origin}${res.data.url}`;
      const tokenMatch = res.data.url.match(/access_token=([^&]+)/);
      const tokenVal = tokenMatch ? tokenMatch[1] : "";
      
      if (onlyToken && tokenVal) {
        await navigator.clipboard.writeText(tokenVal);
        setCopiedToken(true);
        setTimeout(() => setCopiedToken(false), 3000);
      } else {
        await navigator.clipboard.writeText(url);
        setCopiedLink(true);
        setTimeout(() => setCopiedLink(false), 3000);
      }
    } catch (e) {
      console.error(e);
      alert("Failed to generate station link / pairing token");
    }
  };

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const reqs: Promise<any>[] = [axios.get("/api/overlays")];
        if (currentSlug && isStartGgTournament) reqs.push(axios.get(`/api/tournaments/${currentSlug}/streams`));
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
  }, [currentSlug, isStartGgTournament]);

  const selectedStream = useMemo(
    () => streams.find(s => s.id === streamId),
    [streams, streamId]
  );
  const derivedUrl = deriveStreamUrl(selectedStream);

  // Preflight name-fallback hint for THIS station (advisory only — the gate
  // never auto-binds it server-side). Offer a one-click bind when start.gg has a
  // by-name match the TO hasn't explicitly selected yet.
  const gateStation = useMemo(
    () => streamGate?.stations.find(s => s.id === station.id),
    [streamGate, station.id]
  );
  const suggestedId = gateStation?.suggested_stream_id || null;
  const suggestedStream = useMemo(
    () => (suggestedId
      ? (streams.find(s => s.id === suggestedId)
         || streamGate?.startgg_streams.find(s => s.id === suggestedId))
      : undefined),
    [suggestedId, streams, streamGate]
  );
  const showAutoBind = !!suggestedId && streamId !== suggestedId;

  // One-click bind: persist the suggested startgg_stream_id, reflect it in the
  // dropdown, refresh the parent station list, then immediately re-run the
  // preflight so the dashboard banner + ⚠📺 badges clear without a manual reload.
  const handleAutoBind = async () => {
    if (!suggestedId) return;
    setBinding(true);
    try {
      await axios.patch(`/api/stations/${station.id}`, { startgg_stream_id: suggestedId });
      setStreamId(suggestedId);
      onSaved();  // refresh parent's station list (does NOT close the modal)
      if (currentSlug) {
        const res = await axios.get(`/api/tournaments/${currentSlug}/verify-stream`);
        setStreamGate(res.data);  // store update → banner/badges react instantly
      }
    } catch (e: any) {
      alert(e.response?.data?.detail || e.message || "Auto-bind failed");
    } finally {
      setBinding(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // Send only the fields that materially changed — exclude_unset on the
      // backend means we don't have to think about defaults.
      await axios.patch(`/api/stations/${station.id}`, {
        name: name.trim() || station.name,
        hidden,
        bot_enabled: botEnabled,
        ...(isStartGgTournament ? { startgg_stream_id: streamId || "" } : {}),
        stream_url: streamUrlOverride || "",    // empty = use derived
        active_overlay: activeOverlay || "",    // empty = clear
        event_id: eventId || "",                // empty = unbind (any event)
        is_stream_station: isStreamStation,
        room_name_or_id: roomNameOrId.trim() || "",  // empty = clear
        room_password: roomPassword || "",            // empty = clear
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
          {/* Station Agent & OBS Link / Pairing Token */}
          <div className="p-3.5 rounded-lg bg-cyan-950/30 border border-cyan-500/40 flex flex-col gap-2.5 shadow-inner">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-cyan-300 flex items-center gap-1.5">
                <span>🔑</span> Station Agent & OBS Token
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleCopyStationLink(true)}
                  className="px-2.5 py-1 text-xs font-bold rounded bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 border border-cyan-500/40 transition cursor-pointer"
                  title="Copy only the Pairing Token value"
                >
                  {copiedToken ? "✓ Token Copied!" : "📋 Copy Token"}
                </button>
                <button
                  type="button"
                  onClick={() => handleCopyStationLink(false)}
                  className="px-2.5 py-1 text-xs font-bold rounded bg-blue-600/30 text-blue-300 hover:bg-blue-600/50 border border-blue-500/40 transition cursor-pointer"
                  title="Copy full OBS overlay link"
                >
                  {copiedLink ? "✓ Link Copied!" : "🔗 Copy Full Link"}
                </button>
              </div>
            </div>
            <p className="text-[11px] text-textDim leading-relaxed">
              Click <strong>Copy Token</strong> to paste into the <em>Pairing Token</em> field in Station Agent, or <strong>Copy Full Link</strong> to use directly in OBS or Station Agent.
            </p>
          </div>

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

          {/* Provider stream queue exists only for Start.gg. */}
          {isStartGgTournament ? <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-black/25 border border-white/5">
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
            {showAutoBind && (
              <button
                type="button"
                onClick={handleAutoBind}
                disabled={binding}
                title={`Bind this station to the start.gg stream "${suggestedStream?.name}" matched by name`}
                className="flex items-center gap-1.5 self-start rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-xs font-bold text-emerald-300 hover:bg-emerald-500/20 transition-colors disabled:opacity-50 disabled:pointer-events-none"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                {binding ? "Binding…" : `Auto-bind to "${suggestedStream?.name ?? "stream"}"`}
              </button>
            )}
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
          </div> : (
            <div className="rounded-lg border border-white/5 bg-black/25 p-3 text-xs leading-relaxed text-textDim">
              <span className="font-semibold text-white">Local station & overlay</span><br />
              This Challonge tournament uses the station, Browser Source, Discord and OBS locally. aiTOB does not create or update a provider stream queue.
            </div>
          )}

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
              {isStartGgTournament ? 'Leave blank to auto-derive from the Start.gg stream. Override for Kick, restream pages, etc.' : 'Optional public channel or Browser Source link for this local station.'}
            </span>
          </label>

          {/* ── Stream Station (green-room) ── */}
          <div className="flex flex-col gap-3 p-3 rounded-lg bg-black/25 border border-accentYellow/20">
            <label className="flex items-center justify-between cursor-pointer">
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-semibold text-gray-200">Stream Station</span>
                <span className="text-xs text-textDim">Eligible to host stream-flagged matches via the green-room flow</span>
              </div>
              <input
                type="checkbox"
                checked={isStreamStation}
                onChange={e => setIsStreamStation(e.target.checked)}
                className="w-4 h-4 accent-accentYellow cursor-pointer rounded"
              />
            </label>

            {isStreamStation && (
              <>
                {/* Event binding */}
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-semibold text-gray-300">Bound Event (game)</span>
                  <select
                    value={eventId}
                    onChange={e => setEventId(e.target.value)}
                    className="bg-black/40 border border-white/10 rounded px-2.5 py-1 text-sm text-white focus:outline-none focus:border-accentYellow/50"
                  >
                    <option value="" className="text-black">Any event (not recommended)</option>
                    {events.map(ev => (
                      <option key={ev.id} value={ev.id} className="text-black">{ev.name}</option>
                    ))}
                  </select>
                  <span className="text-xs text-textDim">
                    Stream matches only route here when the match's event matches. Prevents cross-game routing (e.g. a Tekken match landing on an SF6 station).
                  </span>
                </label>

                {/* Lobby credentials */}
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-semibold text-gray-300">Lobby Name / ID</span>
                  <input
                    type="text"
                    value={roomNameOrId}
                    onChange={e => setRoomNameOrId(e.target.value)}
                    placeholder="FNC-STREAM-1"
                    className="bg-black/40 border border-white/10 rounded px-2.5 py-1 text-sm text-white focus:outline-none focus:border-accentYellow/50 placeholder:text-textDim"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-semibold text-gray-300">Lobby Password</span>
                  <input
                    type="text"
                    value={roomPassword}
                    onChange={e => setRoomPassword(e.target.value)}
                    placeholder="1234"
                    className="bg-black/40 border border-white/10 rounded px-2.5 py-1 text-sm text-white focus:outline-none focus:border-accentYellow/50 placeholder:text-textDim"
                  />
                  <span className="text-xs text-textDim">
                    Delivered privately to both players by DM — only after they both check in.
                  </span>
                </label>
              </>
            )}
          </div>

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
