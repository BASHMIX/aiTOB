import axios from 'axios';

export interface OverlayAssetBundle {
  filename: string;
  mimeType: string;
  dataUrl: string;
  originalUrl: string;
}

export interface SingleOverlayPackage {
  format: 'aitob-overlay';
  version: 2;
  exportedAt: string;
  name: string;
  config: any;
  assets?: Record<string, OverlayAssetBundle>;
}

export interface MultiOverlayPackage {
  format: 'aitob-package';
  version: 2;
  exportedAt: string;
  stationId?: string;
  stationName?: string;
  overlays: Array<{
    name: string;
    config: any;
  }>;
  assets?: Record<string, OverlayAssetBundle>;
}

export type OverlayImportPackage = SingleOverlayPackage | MultiOverlayPackage;

/**
 * Recursively find all local asset URLs (/static/assets/...) in an overlay configuration
 */
export function extractAssetUrls(obj: any, foundUrls: Set<string> = new Set()): Set<string> {
  if (!obj) return foundUrls;

  if (typeof obj === 'string') {
    if (obj.startsWith('/static/assets/') || obj.startsWith('/static/')) {
      foundUrls.add(obj);
    }
  } else if (Array.isArray(obj)) {
    for (const item of obj) {
      extractAssetUrls(item, foundUrls);
    }
  } else if (typeof obj === 'object') {
    for (const key of Object.keys(obj)) {
      extractAssetUrls(obj[key], foundUrls);
    }
  }
  return foundUrls;
}

/**
 * Convert a remote/local URL into a base64 DataURL asset bundle
 */
export async function bundleAsset(url: string): Promise<OverlayAssetBundle | null> {
  try {
    const res = await axios.get(url, { responseType: 'blob' });
    const blob = res.data as Blob;
    const cleanUrl = url.split('?')[0];
    const filename = cleanUrl.split('/').pop() || `asset_${Date.now()}`;

    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });

    return {
      filename,
      mimeType: blob.type || 'application/octet-stream',
      dataUrl,
      originalUrl: url,
    };
  } catch (err) {
    console.warn(`[OverlayBundle] Could not bundle asset at ${url}:`, err);
    return null;
  }
}

/**
 * Bundle all referenced local assets for a list of configs
 */
export async function bundleAllAssets(
  configs: any[],
  onProgress?: (current: number, total: number) => void
): Promise<Record<string, OverlayAssetBundle>> {
  const allUrls = new Set<string>();
  for (const config of configs) {
    extractAssetUrls(config, allUrls);
  }

  const urlList = Array.from(allUrls);
  const assets: Record<string, OverlayAssetBundle> = {};

  let current = 0;
  for (const url of urlList) {
    current++;
    if (onProgress) onProgress(current, urlList.length);
    const bundle = await bundleAsset(url);
    if (bundle) {
      assets[url] = bundle;
    }
  }

  return assets;
}

/**
 * Trigger a browser download for a JSON payload
 */
export function triggerJsonDownload(filename: string, payload: any) {
  const jsonStr = JSON.stringify(payload, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = href;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(href);
}

/**
 * Export a single overlay slide with bundled assets
 */
export async function exportSingleOverlaySlide(
  name: string,
  config: any,
  onProgress?: (msg: string) => void
): Promise<void> {
  if (onProgress) onProgress('Collecting assets…');
  const assets = await bundleAllAssets([config], (cur, tot) => {
    if (onProgress) onProgress(`Bundling asset ${cur} of ${tot}…`);
  });

  const payload: SingleOverlayPackage = {
    format: 'aitob-overlay',
    version: 2,
    exportedAt: new Date().toISOString(),
    name,
    config,
    assets: Object.keys(assets).length > 0 ? assets : undefined,
  };

  const safeName = name.replace(/[^a-zA-Z0-9_\-\u0600-\u06FF]/g, '_').toLowerCase();
  triggerJsonDownload(`${safeName}.aitob-overlay.json`, payload);
  if (onProgress) onProgress('Export complete!');
}

/**
 * Export all overlays associated with a station as a package
 */
export async function exportStationOverlayPackage(
  stationId: string,
  stationName: string,
  overlays: Array<{ name: string; config: any }>,
  onProgress?: (msg: string) => void
): Promise<void> {
  if (onProgress) onProgress(`Collecting assets for ${overlays.length} slides…`);
  const assets = await bundleAllAssets(
    overlays.map((o) => o.config),
    (cur, tot) => {
      if (onProgress) onProgress(`Bundling asset ${cur} of ${tot}…`);
    }
  );

  const payload: MultiOverlayPackage = {
    format: 'aitob-package',
    version: 2,
    exportedAt: new Date().toISOString(),
    stationId,
    stationName,
    overlays,
    assets: Object.keys(assets).length > 0 ? assets : undefined,
  };

  const safeName = (stationName || stationId).replace(/[^a-zA-Z0-9_\-\u0600-\u06FF]/g, '_').toLowerCase();
  triggerJsonDownload(`${safeName}-station-package.aitob-package.json`, payload);
  if (onProgress) onProgress('Package export complete!');
}

/**
 * Convert base64 dataUrl back to a File
 */
export function dataUrlToFile(dataUrl: string, filename: string, defaultMime = 'application/octet-stream'): File {
  const parts = dataUrl.split(',');
  const mimeMatch = parts[0].match(/:(.*?);/);
  const mimeType = mimeMatch ? mimeMatch[1] : defaultMime;
  const binaryString = atob(parts[1]);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return new File([bytes], filename, { type: mimeType });
}

/**
 * Recursively remap old URLs to newly uploaded URLs in an overlay config
 */
export function remapConfigUrls(obj: any, urlMap: Record<string, string>): any {
  if (!obj) return obj;

  if (typeof obj === 'string') {
    if (urlMap[obj]) {
      return urlMap[obj];
    }
    // Also check if any substring matches
    for (const [oldUrl, newUrl] of Object.entries(urlMap)) {
      if (obj === oldUrl) return newUrl;
    }
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => remapConfigUrls(item, urlMap));
  }

  if (typeof obj === 'object') {
    const copy: Record<string, any> = {};
    for (const [k, v] of Object.entries(obj)) {
      copy[k] = remapConfigUrls(v, urlMap);
    }
    return copy;
  }

  return obj;
}

export interface ImportResult {
  mode: 'single' | 'package';
  importedCount: number;
  names: string[];
  activeName: string;
}

/**
 * Import an overlay JSON package, upload bundled assets to the server, and register overlays
 */
export async function importOverlayPackageFile(
  file: File,
  stationId: string,
  onProgress?: (msg: string) => void
): Promise<ImportResult> {
  if (onProgress) onProgress('Reading package file…');
  const text = await file.text();
  const data = JSON.parse(text) as OverlayImportPackage;

  // 1. Upload bundled assets (if any) and construct urlMap
  const urlMap: Record<string, string> = {};
  if (data.assets && Object.keys(data.assets).length > 0) {
    const assetEntries = Object.entries(data.assets);
    let uploadedCount = 0;

    for (const [origUrl, assetBundle] of assetEntries) {
      uploadedCount++;
      if (onProgress) onProgress(`Restoring asset (${uploadedCount}/${assetEntries.length}): ${assetBundle.filename}…`);

      try {
        const assetFile = dataUrlToFile(assetBundle.dataUrl, assetBundle.filename, assetBundle.mimeType);
        const formData = new FormData();
        formData.append('file', assetFile);

        const uploadRes = await axios.post<{ name: string; url: string }>('/api/assets/upload', formData);
        if (uploadRes.data?.url) {
          urlMap[origUrl] = uploadRes.data.url;
        }
      } catch (uploadErr) {
        console.warn(`[OverlayBundle] Failed to upload asset ${assetBundle.filename}, retaining original URL:`, uploadErr);
        urlMap[origUrl] = origUrl;
      }
    }
  }

  // 2. Process overlays
  const overlaysToImport: Array<{ name: string; config: any }> = [];

  if (data.format === 'aitob-package' && Array.isArray((data as MultiOverlayPackage).overlays)) {
    overlaysToImport.push(...(data as MultiOverlayPackage).overlays);
  } else if (data.format === 'aitob-overlay' || (data as any).name) {
    overlaysToImport.push({
      name: (data as SingleOverlayPackage).name || 'Imported Overlay',
      config: (data as SingleOverlayPackage).config || {},
    });
  } else {
    throw new Error('Unrecognized overlay format. Expected .aitob-overlay.json or .aitob-package.json');
  }

  const importedNames: string[] = [];
  let index = 0;

  for (const item of overlaysToImport) {
    index++;
    if (onProgress) onProgress(`Saving slide (${index}/${overlaysToImport.length}): ${item.name}…`);

    const remappedConfig = remapConfigUrls(item.config, urlMap);

    // Save to database
    await axios.post('/api/overlays', {
      name: item.name,
      config: remappedConfig,
    });

    // Associate with station
    try {
      await axios.post(`/api/stations/${stationId}/overlays`, {
        overlay_name: item.name,
      });
    } catch {
      // Ignore if already associated
    }

    importedNames.push(item.name);
  }

  const activeName = importedNames[0] || '';
  if (activeName) {
    try {
      await axios.post(`/api/stations/${stationId}/active-overlay`, {
        overlay_name: activeName,
      });
    } catch {
      // Ignore
    }
  }

  if (onProgress) onProgress('Import complete!');

  return {
    mode: data.format === 'aitob-package' ? 'package' : 'single',
    importedCount: importedNames.length,
    names: importedNames,
    activeName,
  };
}
