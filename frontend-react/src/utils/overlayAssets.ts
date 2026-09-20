export const PLAYER_IMAGE_PLACEHOLDER = '/static/player_placeholder.jpg';
export const FLAG_IMAGE_PLACEHOLDER = '/static/flag_placeholder.png';

const imageLoadCache = new Map<string, Promise<boolean>>();

export function overlayImagePlaceholder(elementId: string): string {
  return elementId.toLowerCase().includes('flag')
    ? FLAG_IMAGE_PLACEHOLDER
    : PLAYER_IMAGE_PLACEHOLDER;
}

export function resolveOverlayImageSource(elementId: string, source?: string | null): string {
  const normalized = typeof source === 'string' ? source.trim() : '';
  return normalized || overlayImagePlaceholder(elementId);
}

export function overlayImageLayout(
  elementId: string,
  containerWidth?: number,
  containerHeight?: number,
) {
  if (!elementId.toLowerCase().includes('flag')) {
    return {
      width: '100%' as const,
      height: '100%' as const,
      objectFit: 'contain' as const,
    };
  }

  const availableWidth = Number(containerWidth) > 0 ? Number(containerWidth) : 120;
  const availableHeight = Number(containerHeight) > 0 ? Number(containerHeight) : 90;
  const flagAspectRatio = 4 / 3;
  const height = Math.min(availableHeight, availableWidth / flagAspectRatio);
  const width = height * flagAspectRatio;

  return {
    width,
    height,
    objectFit: 'contain' as const,
    position: 'absolute' as const,
    left: '50%',
    top: '50%',
    transform: 'translate(-50%, -50%)',
  };
}

export function preloadImageSource(source: string, timeoutMs = 8000): Promise<boolean> {
  const normalized = source.trim();
  if (!normalized) return Promise.resolve(false);

  const cached = imageLoadCache.get(normalized);
  if (cached) return cached;

  const request = new Promise<boolean>((resolve) => {
    const image = new Image();
    let settled = false;

    const finish = (loaded: boolean) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      resolve(loaded);
    };

    const finishAfterDecode = () => {
      if (typeof image.decode !== 'function') {
        finish(true);
        return;
      }
      image.decode().then(() => finish(true)).catch(() => finish(true));
    };

    const timer = window.setTimeout(() => finish(false), timeoutMs);
    image.onload = finishAfterDecode;
    image.onerror = () => finish(false);
    image.src = normalized;

    if (image.complete) {
      if (image.naturalWidth > 0) finishAfterDecode();
      else finish(false);
    }
  });

  imageLoadCache.set(normalized, request);
  void request.then((loaded) => {
    // Successful images stay warm for the lifetime of the overlay. A failed
    // remote URL may recover later, so do not permanently cache its failure.
    if (!loaded) imageLoadCache.delete(normalized);
  });
  return request;
}

export async function prepareOverlayImageSource(
  elementId: string,
  source?: string | null,
): Promise<string> {
  const fallback = overlayImagePlaceholder(elementId);
  const requested = resolveOverlayImageSource(elementId, source);

  if (await preloadImageSource(requested)) return requested;
  await preloadImageSource(fallback);
  return fallback;
}

interface OverlayConfigLike {
  elements?: Record<string, any>;
  background_url?: string;
  [key: string]: any;
}

export async function prepareOverlayAssets<T extends OverlayConfigLike>(config: T): Promise<T> {
  const prepared = {
    ...config,
    elements: { ...(config.elements || {}) },
  } as T;

  const imageEntries = Object.entries(prepared.elements || {})
    .filter(([, element]) => element?.type === 'image' && element?.visible !== false);

  await Promise.all(imageEntries.map(async ([id, element]) => {
    const src = await prepareOverlayImageSource(id, element.src);
    prepared.elements![id] = { ...element, src };
  }));

  const backgroundUrl = typeof prepared.background_url === 'string'
    ? prepared.background_url.trim()
    : '';
  if (backgroundUrl && !(await preloadImageSource(backgroundUrl))) {
    prepared.background_url = '';
  } else {
    prepared.background_url = backgroundUrl;
  }

  return prepared;
}

export async function waitForOverlayCanvasAssets(
  canvas: HTMLElement | null,
  backgroundUrl?: string,
): Promise<void> {
  if (!canvas) return;

  const images = Array.from(canvas.querySelectorAll<HTMLImageElement>('img[data-overlay-element-id]'));
  await Promise.all(images.map(async (image) => {
    const elementId = image.dataset.overlayElementId || '';
    const preparedSource = await prepareOverlayImageSource(
      elementId,
      image.currentSrc || image.getAttribute('src'),
    );
    if (image.getAttribute('src') !== preparedSource) image.src = preparedSource;
  }));

  const normalizedBackground = typeof backgroundUrl === 'string' ? backgroundUrl.trim() : '';
  if (normalizedBackground) await preloadImageSource(normalizedBackground);
}
