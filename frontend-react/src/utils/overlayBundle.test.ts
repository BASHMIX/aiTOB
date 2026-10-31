import { describe, it, expect } from 'vitest';
import { extractAssetUrls, remapConfigUrls, dataUrlToFile } from './overlayBundle';

describe('overlayBundle utilities', () => {
  it('extracts all /static/assets/ URLs recursively from complex config', () => {
    const config = {
      background_url: '/static/assets/bg.png',
      global_font_url: '/static/assets/font.woff2',
      font_library: [
        { name: 'Custom Font', url: '/static/assets/custom-font.woff2', family: 'Custom' },
        { name: 'Google Font', url: 'https://fonts.googleapis.com/css', family: 'Google' },
      ],
      elements: {
        'el-1': {
          type: 'image',
          url: '/static/assets/logo.png',
        },
        'el-2': {
          type: 'text',
          text: 'Hello',
        },
      },
    };

    const urls = extractAssetUrls(config);
    expect(urls.has('/static/assets/bg.png')).toBe(true);
    expect(urls.has('/static/assets/font.woff2')).toBe(true);
    expect(urls.has('/static/assets/custom-font.woff2')).toBe(true);
    expect(urls.has('/static/assets/logo.png')).toBe(true);
    expect(urls.has('https://fonts.googleapis.com/css')).toBe(false);
    expect(urls.size).toBe(4);
  });

  it('remaps old URLs to new URLs accurately across nested configs', () => {
    const config = {
      background_url: '/static/assets/old_bg.png',
      elements: {
        'el-img': {
          url: '/static/assets/old_logo.png',
        },
      },
    };

    const urlMap = {
      '/static/assets/old_bg.png': '/static/assets/new_server_bg.png',
      '/static/assets/old_logo.png': '/static/assets/new_server_logo.png',
    };

    const remapped = remapConfigUrls(config, urlMap);
    expect(remapped.background_url).toBe('/static/assets/new_server_bg.png');
    expect(remapped.elements['el-img'].url).toBe('/static/assets/new_server_logo.png');
  });

  it('converts dataUrl to File with correct filename and mimeType', () => {
    // 1x1 transparent PNG in base64
    const dataUrl = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';
    const file = dataUrlToFile(dataUrl, 'test.png', 'image/png');

    expect(file.name).toBe('test.png');
    expect(file.type).toBe('image/png');
    expect(file.size).toBeGreaterThan(0);
  });
});
