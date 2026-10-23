import * as htmlToImage from 'html-to-image';

export interface ExportOptions {
  width: number;
  height: number;
  filename?: string;
  skipDownload?: boolean;
}

export interface ExportResult {
  blob: Blob;
  byteSize: number;
  sha256: string;
}

export function downloadPngBlob(blob: Blob, filename = 'tournament-results.png'): void {
  if (typeof document === 'undefined') return;
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function computeBlobSha256(blob: Blob): Promise<string> {
  const arrayBuffer = await blob.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

export async function exportSceneToPng(
  element: HTMLElement,
  options: ExportOptions,
): Promise<ExportResult> {
  if (!element) {
    throw new Error('Export rasterization failed: target element not found');
  }

  // Ensure browser fonts are ready before rasterizing
  if (typeof document !== 'undefined' && 'fonts' in document) {
    try {
      await document.fonts.ready;
    } catch {
      // Ignore font readiness timeout
    }
  }

  let blob: Blob | null = null;
  try {
    blob = await htmlToImage.toBlob(element, {
      pixelRatio: 1,
      width: options.width,
      height: options.height,
      cacheBust: true,
      skipAutoScale: true,
    });
  } catch (err: any) {
    throw new Error(`Export rasterization failed: ${err?.message || 'unknown error'}`);
  }

  if (!blob) {
    throw new Error('Export rasterization failed: produced empty image blob');
  }

  const sha256 = await computeBlobSha256(blob);

  if (!options.skipDownload && typeof document !== 'undefined') {
    downloadPngBlob(blob, options.filename);
  }

  return {
    blob,
    byteSize: blob.size,
    sha256,
  };
}
