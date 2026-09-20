import { useEffect, useState, useCallback, useRef } from 'react';
import { useHubStore } from '@/store/useHubStore';

export function ConnectionLines() {
  const { matches } = useHubStore();
  const [lines, setLines] = useState<
    Array<{ id: string; path: string; startX: number; startY: number; endX: number; endY: number }>
  >([]);
  const containerRef = useRef<HTMLDivElement>(null);

  // Active matches assigned to a station
  const activeMatches = matches.filter(
    (m) => (m.status === 'in_progress' || m.status === 'called') && m.station_id
  );

  const calculateLines = useCallback(() => {
    if (!containerRef.current) return;
    const containerRect = containerRef.current.getBoundingClientRect();
    const newLines: Array<{ id: string; path: string; startX: number; startY: number; endX: number; endY: number }> = [];

    activeMatches.forEach((m) => {
      const matchEl = document.getElementById(`active-match-${m.set_id}`);
      const stationEl = document.getElementById(`station-${m.station_id}`);

      if (matchEl && stationEl) {
        const mRect = matchEl.getBoundingClientRect();
        const sRect = stationEl.getBoundingClientRect();

        // Start point: bottom center of the active match card
        const startX = (mRect.left + mRect.right) / 2 - containerRect.left;
        const startY = mRect.bottom - containerRect.top;

        // End point: top center of the station card
        const endX = (sRect.left + sRect.right) / 2 - containerRect.left;
        const endY = sRect.top - containerRect.top;

        // Curved Bezier node connection curve (down and then up)
        const deltaY = Math.max(30, endY - startY);
        const cpY1 = startY + Math.min(60, deltaY * 0.45);
        const cpY2 = endY - Math.min(60, deltaY * 0.45);

        // Avoid exactly 0-width bounding boxes which break SVG gradients and filters in some browsers
        const adjustedEndX = Math.abs(startX - endX) < 0.1 ? endX + 0.1 : endX;
        const path = `M ${startX} ${startY} C ${startX} ${cpY1}, ${adjustedEndX} ${cpY2}, ${adjustedEndX} ${endY}`;

        newLines.push({
          id: `${m.set_id}-${m.station_id}`,
          path,
          startX,
          startY,
          endX: adjustedEndX,
          endY,
        });
      }
    });

    // Check if lines actually changed to prevent state thrashing
    const serializedNew = JSON.stringify(newLines);
    const serializedOld = JSON.stringify(lines);
    if (serializedNew !== serializedOld) {
      setLines(newLines);
    }
  }, [activeMatches, lines]);

  useEffect(() => {
    let animationFrameId: number | null = null;

    const scheduleUpdate = () => {
      if (animationFrameId !== null) return;
      animationFrameId = requestAnimationFrame(() => {
        calculateLines();
        animationFrameId = null;
      });
    };

    scheduleUpdate();

    // Listen to container resizing
    const observer = new ResizeObserver(() => {
      scheduleUpdate();
    });

    if (containerRef.current) {
      observer.observe(containerRef.current);
      if (containerRef.current.parentElement) {
        observer.observe(containerRef.current.parentElement);
      }
    }

    // Listen to parent tab scroll container
    const scrollEl = containerRef.current?.closest('.overflow-y-auto');
    if (scrollEl) {
      scrollEl.addEventListener('scroll', scheduleUpdate, { passive: true });
    }

    window.addEventListener('resize', scheduleUpdate, { passive: true });

    // Brief delayed rechecks to align after entrance animations and DOM renders
    const t1 = setTimeout(scheduleUpdate, 100);
    const t2 = setTimeout(scheduleUpdate, 350);

    return () => {
      observer.disconnect();
      if (scrollEl) {
        scrollEl.removeEventListener('scroll', scheduleUpdate);
      }
      window.removeEventListener('resize', scheduleUpdate);
      clearTimeout(t1);
      clearTimeout(t2);
      if (animationFrameId !== null) {
        cancelAnimationFrame(animationFrameId);
      }
    };
  }, [calculateLines]);

  if (lines.length === 0) {
    return <div ref={containerRef} className="absolute inset-0 pointer-events-none" />;
  }

  return (
    <div ref={containerRef} className="absolute inset-0 pointer-events-none" style={{ zIndex: 12 }}>
      <svg className="w-full h-full absolute inset-0 overflow-visible">
        <defs>
          <linearGradient id="stream-flow-glow" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.9" />
            <stop offset="50%" stopColor="#eab308" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0.9" />
          </linearGradient>
          <filter id="stream-line-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
        {lines.map((l) => (
          <g key={l.id}>
            {/* Background glowing line */}
            <path
              d={l.path}
              fill="none"
              stroke="#38bdf8"
              strokeWidth="5"
              strokeOpacity="0.22"
              filter="url(#stream-line-glow)"
            />
            {/* Foreground cable line with flowing animation */}
            <path
              d={l.path}
              fill="none"
              stroke="url(#stream-flow-glow)"
              strokeWidth="2.5"
              strokeDasharray="8,6"
              className="stream-wire-flow"
            />
            {/* Source connector port */}
            <circle cx={l.startX} cy={l.startY} r="4" fill="#38bdf8" stroke="#090d16" strokeWidth="2" />
            <circle cx={l.startX} cy={l.startY} r="1.8" fill="#ffffff" />

            {/* Destination connector port */}
            <circle cx={l.endX} cy={l.endY} r="4" fill="#22c55e" stroke="#090d16" strokeWidth="2" />
            <circle cx={l.endX} cy={l.endY} r="1.8" fill="#ffffff" />
          </g>
        ))}
      </svg>
      <style>{`
        @keyframes streamWireFlow {
          to {
            stroke-dashoffset: -28;
          }
        }
        .stream-wire-flow {
          animation: streamWireFlow 1.6s linear infinite;
        }
      `}</style>
    </div>
  );
}
