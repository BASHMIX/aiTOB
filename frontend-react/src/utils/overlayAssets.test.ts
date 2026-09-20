import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';
import {
  FLAG_IMAGE_PLACEHOLDER,
  PLAYER_IMAGE_PLACEHOLDER,
  prepareOverlayAssets,
  overlayImageLayout,
  resolveOverlayImageSource,
} from './overlayAssets';

class MockImage {
  complete = false;
  naturalWidth = 0;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private value = '';

  get src() {
    return this.value;
  }

  set src(value: string) {
    this.value = value;
    queueMicrotask(() => {
      this.complete = true;
      if (value.includes('broken')) {
        this.onerror?.();
      } else {
        this.naturalWidth = 100;
        this.onload?.();
      }
    });
  }

  decode() {
    return Promise.resolve();
  }
}

describe('overlay asset preparation', () => {
  beforeAll(() => {
    vi.stubGlobal('Image', MockImage);
  });

  afterAll(() => {
    vi.unstubAllGlobals();
  });

  it('assigns local placeholders when image sources are missing', async () => {
    const prepared = await prepareOverlayAssets({
      elements: {
        p1_avatar: { type: 'image', visible: true, src: '' },
        p1_flag: { type: 'image', visible: true, src: undefined },
      },
      background_url: '',
    });

    expect(prepared.elements.p1_avatar.src).toBe(PLAYER_IMAGE_PLACEHOLDER);
    expect(prepared.elements.p1_flag.src).toBe(FLAG_IMAGE_PLACEHOLDER);
  });

  it('replaces failed images and removes a failed optional background', async () => {
    const prepared = await prepareOverlayAssets({
      elements: {
        custom_art: { type: 'image', visible: true, src: 'https://assets.test/broken-art.png' },
      },
      background_url: 'https://assets.test/broken-background.png',
    });

    expect(prepared.elements.custom_art.src).toBe(PLAYER_IMAGE_PLACEHOLDER);
    expect(prepared.background_url).toBe('');
  });

  it('keeps a valid source unchanged', async () => {
    const source = 'https://assets.test/ready-art.png';
    const prepared = await prepareOverlayAssets({
      elements: {
        custom_art: { type: 'image', visible: true, src: source },
      },
    });

    expect(prepared.elements.custom_art.src).toBe(source);
    expect(resolveOverlayImageSource('p2_flag', null)).toBe(FLAG_IMAGE_PLACEHOLDER);
  });

  it('renders flags at their undistorted 4:3 source ratio', () => {
    expect(overlayImageLayout('p1_flag', 120, 120)).toMatchObject({
      width: 120,
      height: 90,
      objectFit: 'contain',
      left: '50%',
      top: '50%',
      transform: 'translate(-50%, -50%)',
    });
    expect(overlayImageLayout('p2_flag', 200, 50)).toMatchObject({
      width: 50 * (4 / 3),
      height: 50,
    });
  });
});
