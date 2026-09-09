import { useEffect, useRef, useState, type ReactNode } from 'react';

export type DQPlayer = 'p1' | 'p2';

interface DQPlayerMenuProps {
  players: readonly [{ name?: string | null }, { name?: string | null }];
  onSelect: (player: DQPlayer) => void;
  /** Start.gg retains its existing double-DQ option; Challonge intentionally omits it. */
  onBothPlayers?: () => void;
  renderTrigger: (control: { open: boolean; toggle: () => void }) => ReactNode;
  onOpenChange?: (open: boolean) => void;
  menuPositionClassName?: string;
}

/**
 * Shared manual-DQ picker for Match Dashboard and the On-Stream card.
 * The menu deliberately presents only individual entrants for Challonge;
 * it does not need an explanatory warning to enforce that provider rule.
 */
export function DQPlayerMenu({
  players,
  onSelect,
  onBothPlayers,
  renderTrigger,
  onOpenChange,
  menuPositionClassName = 'right-0 top-full mt-1.5',
}: DQPlayerMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    onOpenChange?.(open);
  }, [open, onOpenChange]);

  useEffect(() => {
    const closeWhenOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', closeWhenOutside);
    return () => document.removeEventListener('mousedown', closeWhenOutside);
  }, []);

  const choose = (player: DQPlayer) => {
    setOpen(false);
    onSelect(player);
  };

  return (
    <div className="relative" ref={ref}>
      {renderTrigger({ open, toggle: () => setOpen(value => !value) })}
      {open && (
        <div className={`absolute z-[100] min-w-[150px] overflow-hidden rounded-md border border-red-500/40 bg-cardDark p-1 text-left shadow-2xl animate-slideUp ${menuPositionClassName}`}>
          <div className="mb-1 border-b border-white/5 px-2.5 py-1 text-[9px] font-bold uppercase tracking-widest text-red-400">DQ who?</div>
          <button onClick={() => choose('p1')} className="w-full truncate rounded px-3 py-2 text-left text-xs text-white transition-colors hover:bg-red-500/10">
            {players[0].name || 'P1'}
          </button>
          <button onClick={() => choose('p2')} className="w-full truncate rounded px-3 py-2 text-left text-xs text-white transition-colors hover:bg-red-500/10">
            {players[1].name || 'P2'}
          </button>
          {onBothPlayers && (
            <button onClick={() => { setOpen(false); onBothPlayers(); }} className="mt-1 w-full rounded border-t border-white/5 px-3 py-2 text-left text-xs font-bold italic text-red-500 transition-colors hover:bg-red-500/10">
              Both Players
            </button>
          )}
        </div>
      )}
    </div>
  );
}
