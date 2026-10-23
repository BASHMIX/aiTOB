import { describe, it, expect, vi, beforeEach } from 'vitest';
import { exportSceneToPng, computeBlobSha256 } from './resultsExport';
import * as htmlToImage from 'html-to-image';

vi.mock('html-to-image', () => ({
  toPng: vi.fn(),
  toBlob: vi.fn(),
}));

describe('resultsExport utility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('computes correct SHA-256 digest from a blob', async () => {
    const textData = 'test-image-data-aitob';
    const blob = new Blob([textData], { type: 'image/png' });
    const hash = await computeBlobSha256(blob);

    expect(typeof hash).toBe('string');
    expect(hash.length).toBe(64); // 64 hex characters for SHA-256
  });

  it('calls html-to-image with fixed pixelRatio: 1 and canvas dimensions', async () => {
    const mockElement = document.createElement('div');
    mockElement.style.width = '1920px';
    mockElement.style.height = '1080px';
    document.body.appendChild(mockElement);

    const fakeBlob = new Blob(['fake-png-bytes'], { type: 'image/png' });
    vi.mocked(htmlToImage.toBlob).mockResolvedValue(fakeBlob);

    const result = await exportSceneToPng(mockElement, {
      width: 1920,
      height: 1080,
      filename: 'results-top8.png',
      skipDownload: true,
    });

    expect(htmlToImage.toBlob).toHaveBeenCalledWith(
      mockElement,
      expect.objectContaining({
        pixelRatio: 1,
        width: 1920,
        height: 1080,
      }),
    );
    expect(result.byteSize).toBe(fakeBlob.size);
    expect(result.sha256).toBeDefined();

    document.body.removeChild(mockElement);
  });

  it('throws descriptive error if rasterization fails', async () => {
    const mockElement = document.createElement('div');
    vi.mocked(htmlToImage.toBlob).mockRejectedValue(new Error('Canvas tainted by CORS'));

    await expect(
      exportSceneToPng(mockElement, { width: 1920, height: 1080, skipDownload: true }),
    ).rejects.toThrow(/Export rasterization failed/);
  });
});
