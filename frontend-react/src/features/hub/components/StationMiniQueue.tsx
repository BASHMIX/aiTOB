import axios from 'axios';
import { useEffect, useState, useCallback } from 'react';

interface QueuedMatch {
  queue_id: number;
  station_id: string;
  set_id: string;
  sort_order: number;
  p1_name?: string;
  p2_name?: string;
  p1_prefix?: string;
  p2_prefix?: string;
  round_name?: string;
  status?: string;
  busy_players?: {
    player: string;
    station_name: string;
    station_id: string;
    set_id: string;
  }[];
}

interface Props {
  stationId: string;
  onReload: () => void;
  accent?: string;
}

export function StationMiniQueue({ stationId, onReload, accent }: Props) {
  const [queue, setQueue] = useState<QueuedMatch[]>([]);
  const [loading, setLoading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(() => {
    return localStorage.getItem(`station_queue_open_${stationId}`) !== 'false';
  });
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);

  const toggleExpanded = () => {
    setIsExpanded((prev) => {
      const next = !prev;
      localStorage.setItem(`station_queue_open_${stationId}`, String(next));
      return next;
    });
  };

  const loadQueue = useCallback(async () => {
    if (!stationId) return;
    try {
      setLoading(true);
      const res = await axios.get(`/api/stations/${stationId}/queue`);
      setQueue(res.data?.queue || []);
    } catch (e) {
      console.error('Failed to load station queue', e);
    } finally {
      setLoading(false);
    }
  }, [stationId]);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const handleRemove = async (setId: string) => {
    try {
      await axios.delete(`/api/stations/${stationId}/queue/${encodeURIComponent(setId)}`);
      setQueue((prev) => prev.filter((item) => item.set_id !== setId));
      onReload();
    } catch (e) {
      console.error('Failed to remove match from station queue', e);
    }
  };

  const handleMove = async (fromIdx: number, toIdx: number) => {
    if (fromIdx === toIdx || fromIdx < 0 || toIdx < 0 || fromIdx >= queue.length || toIdx >= queue.length) {
      return;
    }
    const updated = [...queue];
    const [moved] = updated.splice(fromIdx, 1);
    updated.splice(toIdx, 0, moved);
    setQueue(updated);

    try {
      await axios.put(`/api/stations/${stationId}/queue/reorder`, {
        set_ids: updated.map((item) => item.set_id),
      });
      onReload();
    } catch (e) {
      console.error('Failed to reorder station queue', e);
      loadQueue(); // revert on failure
    }
  };

  return (
    <div
      className="mt-3 pt-2 border-t border-white/10"
      style={accent ? { borderTopColor: `${accent}33` } : undefined}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-1 text-xs">
        <button
          onClick={toggleExpanded}
          className="flex items-center gap-1.5 font-bold text-textDim hover:text-white transition-colors"
          title={isExpanded ? 'Collapse mini-queue' : 'Expand mini-queue'}
        >
          <span>📋 Stream Queue</span>
          <span
            className={`px-1.5 py-0.2 rounded-full text-[10px] ${
              queue.length > 0 ? 'bg-[#00ffcc]/20 text-[#00ffcc] font-mono font-bold' : 'bg-white/10 text-textDim'
            }`}
            style={accent && queue.length > 0 ? { color: accent, backgroundColor: `${accent}20` } : undefined}
          >
            {queue.length}
          </span>
          <span className="text-[10px] text-textDim/70">{loading ? '⏳' : (isExpanded ? '▲' : '▼')}</span>
        </button>
        {queue.length > 0 && isExpanded && (
          <span className="text-[9px] text-textDim/60 font-sans select-none">Drag to reorder</span>
        )}
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="flex flex-col gap-1.5 mt-1.5">
          {queue.length === 0 ? (
            <div className="text-[10px] text-textDim/60 italic py-2.5 text-center border border-dashed border-white/10 rounded-md bg-black/10 select-none">
              Queue empty. Drag matches here.
            </div>
          ) : (
            queue.map((item, idx) => {
              const isFirst = idx === 0;
              const hasBusyPlayers = Array.isArray(item.busy_players) && item.busy_players.length > 0;
              const p1Display = `${item.p1_prefix ? `[${item.p1_prefix}] ` : ''}${item.p1_name || 'TBD'}`;
              const p2Display = `${item.p2_prefix ? `[${item.p2_prefix}] ` : ''}${item.p2_name || 'TBD'}`;

              return (
                <div
                  key={item.set_id || item.queue_id}
                  draggable
                  onDragStart={(e) => {
                    e.stopPropagation();
                    const payload = {
                      type: 'station_queue_item',
                      fromStationId: stationId,
                      queueIndex: idx,
                      setId: String(item.set_id || item.queue_id),
                      round: item.round_name || '',
                      p1: item.p1_name || '',
                      p2: item.p2_name || '',
                    };
                    e.dataTransfer.setData('application/json', JSON.stringify(payload));
                    e.dataTransfer.setData('text/plain', String(item.set_id || item.queue_id));
                    setDraggedIndex(idx);
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    let fromIndex = draggedIndex;
                    try {
                      const raw = e.dataTransfer.getData('application/json');
                      if (raw) {
                        const parsed = JSON.parse(raw);
                        if (parsed.fromStationId === stationId && typeof parsed.queueIndex === 'number') {
                          fromIndex = parsed.queueIndex;
                        }
                      }
                    } catch {}
                    if (fromIndex !== null && fromIndex !== idx && !isNaN(fromIndex)) {
                      handleMove(fromIndex, idx);
                    }
                    setDraggedIndex(null);
                  }}
                  className={`group relative rounded border p-1.5 transition-all text-xs select-none ${
                    isFirst
                      ? 'border-[#00ffcc]/40 bg-[#00ffcc]/5 shadow-[0_0_8px_rgba(0,255,204,0.08)]'
                      : 'border-white/10 bg-black/20 hover:border-white/20'
                  } ${draggedIndex === idx ? 'opacity-40 border-dashed border-accentYellow' : ''}`}
                >
                  <div className="flex items-center justify-between gap-1.5">
                    {/* Position badge */}
                    <span
                      className={`shrink-0 px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider ${
                        isFirst
                          ? 'bg-[#00ffcc]/20 text-[#00ffcc] border border-[#00ffcc]/40'
                          : 'bg-white/10 text-textDim font-mono'
                      }`}
                      title={isFirst ? 'Feeds Next Match OBS overlay hooks' : undefined}
                    >
                      {isFirst ? '★ Next Up' : `#${idx + 1}`}
                    </span>

                    {/* Match matchup */}
                    <div className="flex-1 min-w-0 flex items-center justify-between gap-1">
                      <span className="truncate text-white font-medium text-[11px]" title={`${p1Display} vs ${p2Display}`}>
                        {p1Display} <span className="text-textDim text-[10px]">vs</span> {p2Display}
                      </span>
                      {item.round_name && (
                        <span className="shrink-0 text-[9px] text-textDim truncate max-w-[80px]" title={item.round_name}>
                          {item.round_name}
                        </span>
                      )}
                    </div>

                    {/* Actions: up/down buttons & remove */}
                    <div className="flex items-center gap-1 opacity-60 group-hover:opacity-100 transition-opacity shrink-0">
                      {idx > 0 && (
                        <button
                          onClick={() => handleMove(idx, idx - 1)}
                          title="Move up"
                          className="text-textDim hover:text-white text-[10px] leading-none px-0.5"
                        >
                          ▲
                        </button>
                      )}
                      {idx < queue.length - 1 && (
                        <button
                          onClick={() => handleMove(idx, idx + 1)}
                          title="Move down"
                          className="text-textDim hover:text-white text-[10px] leading-none px-0.5"
                        >
                          ▼
                        </button>
                      )}
                      <button
                        onClick={() => handleRemove(item.set_id)}
                        title="Remove from queue"
                        className="text-statusRed/70 hover:text-statusRed text-xs font-bold leading-none ml-1 px-1"
                      >
                        ✖
                      </button>
                    </div>
                  </div>

                  {/* Busy player guard warning badge */}
                  {hasBusyPlayers && (
                    <div
                      className="mt-1 flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[9px] text-amber-300 font-semibold"
                      title="Player in this match is currently playing in another active match!"
                    >
                      <span className="animate-pulse">🟡 ⚠️</span>
                      <span className="truncate">
                        {item.busy_players!.map((bp) => `${bp.player} playing on ${bp.station_name}`).join(' · ')}
                      </span>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
