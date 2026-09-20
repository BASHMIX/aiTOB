import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { useHubStore } from '@/store/useHubStore';
import type { OrganizerConsoleOpenRequest } from './OrganizerConsole';

type NotificationTone = 'critical' | 'warning';

interface NotificationItem {
  id: string;
  title: string;
  message: string;
  tone: NotificationTone;
  target: Omit<OrganizerConsoleOpenRequest, 'requestId'>;
}

interface NotificationCenterProps {
  onOpenNotification: (target: Omit<OrganizerConsoleOpenRequest, 'requestId'>) => void;
  refreshSignal?: number;
}

function asText(value: unknown, fallback: string) {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

export function NotificationCenter({ onOpenNotification, refreshSignal = 0 }: NotificationCenterProps) {
  const { currentSlug, status } = useHubStore();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    const items: NotificationItem[] = [];

    if (status.token_scope && (!status.token_scope.valid || !status.token_scope.has_write_scope)) {
      items.push({
        id: 'startgg-token-scope',
        title: 'Start.gg connection impaired',
        message: asText(status.token_scope.error, 'The token is missing the required tournament organizer write scope.'),
        tone: 'critical',
        target: { tab: 'attention', focusKey: 'provider-token' },
      });
    }

    try {
      const [conflictsResult, consoleResult] = await Promise.allSettled([
        axios.get('/api/conflicts'),
        currentSlug ? axios.get(`/api/organizer-console/${currentSlug}`) : Promise.resolve({ data: null }),
      ]);

      const conflicts = conflictsResult.status === 'fulfilled' ? conflictsResult.value.data?.conflicts || [] : [];
      conflicts.forEach((conflict: any) => {
        const p1 = asText(conflict.p1_name, 'Player 1');
        const p2 = asText(conflict.p2_name, 'Player 2');
        items.push({
          id: `conflict-${conflict.id}`,
          title: `Match #${conflict.set_id} conflict`,
          message: `${p1} vs ${p2} needs an organizer decision.`,
          tone: 'critical',
          target: { tab: 'conflicts', conflictId: Number(conflict.id) },
        });
      });

      const attention = consoleResult.status === 'fulfilled' ? consoleResult.value.data?.attention : null;
      if (attention?.provider_outage?.active) {
        items.push({
          id: 'provider-outage',
          title: 'Provider sync unavailable',
          message: asText(attention.provider_outage.message, 'Provider synchronization is unavailable; local state remains readable.'),
          tone: 'critical',
          target: { tab: 'attention', focusKey: 'provider-outage' },
        });
      }
      (attention?.failed_commands || []).forEach((command: any) => {
        items.push({
          id: `provider-command-${command.id}`,
          title: `Provider command ${command.state}`,
          message: `${asText(command.action, 'Command')} · match ${asText(command.set_id, 'unknown')}`,
          tone: 'critical',
          target: { tab: 'attention', focusKey: `provider-command-${command.id}` },
        });
      });
      (attention?.awaiting_verification || []).forEach((command: any) => {
        items.push({
          id: `verification-${command.id}`,
          title: 'Awaiting provider verification',
          message: `${asText(command.action, 'Command')} · match ${asText(command.set_id, 'unknown')}`,
          tone: 'warning',
          target: { tab: 'attention', focusKey: `provider-command-${command.id}` },
        });
      });
    } finally {
      setNotifications(items);
      setLoading(false);
    }
  }, [currentSlug, status.token_scope]);

  useEffect(() => { if (open) void refresh(); }, [open, refresh, refreshSignal]);

  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (open && containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', closeOnOutsideClick);
    return () => document.removeEventListener('mousedown', closeOnOutsideClick);
  }, [open]);

  const countLabel = useMemo(() => notifications.length > 99 ? '99+' : String(notifications.length), [notifications.length]);

  const openNotification = (notification: NotificationItem) => {
    setOpen(false);
    onOpenNotification(notification.target);
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        aria-label={notifications.length ? `Notifications (${notifications.length})` : 'Notifications'}
        aria-expanded={open}
        onClick={() => setOpen((visible) => !visible)}
        className={`relative flex h-10 items-center gap-2 rounded-lg border px-3 text-xs font-bold transition-colors ${notifications.length ? 'border-red-400/40 bg-red-500/10 text-red-100 hover:bg-red-500/20' : 'border-white/10 bg-cardDark/60 text-textDim hover:text-white'}`}
      >
        <span className="text-base" aria-hidden="true">🔔</span>
        <span className="hidden sm:inline">Notifications</span>
        {notifications.length > 0 && <span className="min-w-5 rounded-full bg-statusRed px-1.5 py-0.5 text-center text-[10px] leading-none text-white">{countLabel}</span>}
      </button>

      {open && (
        <div role="dialog" aria-label="Notification center" className="absolute right-0 top-12 z-[60] w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-white/10 bg-[#13171f] shadow-2xl">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <div>
              <h2 className="text-xs font-bold uppercase tracking-widest text-accentYellow">Notification Center</h2>
              <p className="mt-1 text-[10px] text-textDim">Open any item in AI Organizer Console.</p>
            </div>
            <button type="button" onClick={() => void refresh()} className="rounded border border-white/10 px-2 py-1 text-[10px] text-textDim hover:text-white" disabled={loading}>
              {loading ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
          <div className="max-h-[min(28rem,60vh)] overflow-y-auto p-2 custom-scrollbar">
            {loading && notifications.length === 0 ? <p className="px-3 py-8 text-center text-xs text-textDim">Loading notifications…</p> : notifications.length === 0 ? <p className="px-3 py-8 text-center text-xs text-textDim">You’re all caught up.</p> : notifications.map((notification) => (
              <button
                type="button"
                key={notification.id}
                onClick={() => openNotification(notification)}
                className="mb-1.5 block w-full rounded-lg border border-white/5 bg-black/20 p-3 text-left transition hover:border-accentYellow/40 hover:bg-white/5"
              >
                <div className="flex items-start gap-2">
                  <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${notification.tone === 'critical' ? 'bg-statusRed' : 'bg-amber-300'}`} aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block text-xs font-bold text-white">{notification.title}</span>
                    <span className="mt-1 block text-[11px] leading-relaxed text-textDim">{notification.message}</span>
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
