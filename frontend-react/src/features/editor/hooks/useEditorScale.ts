import { useState, useEffect, useRef } from 'react';

export function useEditorScale() {
  const [scale, setScale] = useState<number | null>(null);
  const [autoScale, setAutoScale] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!autoScale) return;
    const container = containerRef.current;
    if (!container) return;

    const handleResize = () => {
      const { clientWidth, clientHeight } = container;
      if (clientWidth > 100 && clientHeight > 100) {
        const newScale = Math.min((clientWidth - 100) / 1920, (clientHeight - 100) / 1080);
        setScale(newScale);
      }
    };

    handleResize();

    const observer = new ResizeObserver(() => {
      handleResize();
    });
    observer.observe(container);

    window.addEventListener('resize', handleResize);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', handleResize);
    };
  }, [autoScale]);

  return { scale, setScale, setAutoScale, containerRef };
}
