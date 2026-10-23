import type { CardVariantOverride, SceneDocumentV2 } from './types';

function scaled(value: number | undefined, factor: number): number | undefined {
  return value === undefined ? undefined : value * factor;
}

function scaleVariant(
  value: Partial<CardVariantOverride>,
  scaleX: number,
  scaleY: number,
  unitScale: number,
): Partial<CardVariantOverride> {
  return {
    ...value,
    x: scaled(value.x, scaleX),
    y: scaled(value.y, scaleY),
    width: scaled(value.width, scaleX),
    height: scaled(value.height, scaleY),
    fontSize: scaled(value.fontSize, unitScale),
    borderRadius: scaled(value.borderRadius, unitScale),
    strokeWidth: scaled(value.strokeWidth, unitScale),
  };
}

/**
 * Reflows a scene into another output profile while preserving the normalized
 * position of every editable node and generated-card slot. This prevents a
 * landscape template from being silently clipped when exporting square or
 * portrait media.
 */
export function resizeSceneDocument(
  source: SceneDocumentV2,
  width: number,
  height: number,
): SceneDocumentV2 {
  const oldWidth = source.canvas.width || width;
  const oldHeight = source.canvas.height || height;
  const scaleX = width / oldWidth;
  const scaleY = height / oldHeight;
  const unitScale = Math.min(scaleX, scaleY);
  const next: SceneDocumentV2 = JSON.parse(JSON.stringify(source));

  next.canvas.width = width;
  next.canvas.height = height;
  if (next.canvas.safeArea) {
    next.canvas.safeArea = {
      top: next.canvas.safeArea.top * scaleY,
      right: next.canvas.safeArea.right * scaleX,
      bottom: next.canvas.safeArea.bottom * scaleY,
      left: next.canvas.safeArea.left * scaleX,
    };
  }

  for (const node of Object.values(next.nodes)) {
    node.x *= scaleX;
    node.y *= scaleY;
    node.width *= scaleX;
    node.height *= scaleY;

    if (node.type === 'text') {
      node.fontSize = scaled(node.fontSize, unitScale);
      node.strokeWidth = scaled(node.strokeWidth, unitScale);
      node.shadowBlur = scaled(node.shadowBlur, unitScale);
      node.shadowOffsetX = scaled(node.shadowOffsetX, scaleX);
      node.shadowOffsetY = scaled(node.shadowOffsetY, scaleY);
    } else if (node.type === 'image' || node.type === 'rect') {
      node.borderRadius = scaled(node.borderRadius, unitScale);
      node.shadowBlur = scaled(node.shadowBlur, unitScale);
      node.shadowOffsetX = scaled(node.shadowOffsetX, scaleX);
      node.shadowOffsetY = scaled(node.shadowOffsetY, scaleY);
      if (node.type === 'rect') node.strokeWidth = scaled(node.strokeWidth, unitScale);
    } else if (node.type === 'circle') {
      node.strokeWidth = scaled(node.strokeWidth, unitScale);
      node.shadowBlur = scaled(node.shadowBlur, unitScale);
      node.shadowOffsetX = scaled(node.shadowOffsetX, scaleX);
      node.shadowOffsetY = scaled(node.shadowOffsetY, scaleY);
    }

    if (node.type === 'group' && node.variants) {
      for (const variant of Object.values(node.variants)) {
        if (!variant) continue;
        for (const [nodeId, override] of Object.entries(variant)) {
          variant[nodeId] = scaleVariant(override, scaleX, scaleY, unitScale);
        }
      }
    }
    if (node.type === 'results-group' && node.customSlots) {
      node.customSlots = node.customSlots.map((slot) => ({
        ...slot,
        x: slot.x * scaleX,
        y: slot.y * scaleY,
        width: slot.width * scaleX,
        height: slot.height * scaleY,
      }));
    }
  }

  return next;
}
