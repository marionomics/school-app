const QUALITY = 0.85;
const SHRINKABLE = new Set(["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"]);

type Named = { type: string; name: string };

export function isHeic(file: Named): boolean {
  return /^image\/hei[cf]$/.test(file.type) || /\.hei[cf]$/i.test(file.name);
}

/** GIF would lose its animation and SVG isn't a photo: those are never
 *  re-encoded, nor is anything that isn't an image. */
export function shouldShrink(file: Named): boolean {
  return SHRINKABLE.has(file.type) || (file.type === "" && isHeic(file));
}

export function fitWithin(w: number, h: number, max: number) {
  const scale = Math.min(1, max / Math.max(w, h));
  return { width: Math.round(w * scale), height: Math.round(h * scale) };
}

export function centerSquare(w: number, h: number) {
  const size = Math.min(w, h);
  return { sx: Math.round((w - size) / 2), sy: Math.round((h - size) / 2), size };
}

function jpegName(name: string): string {
  const dot = name.lastIndexOf(".");
  return `${dot > 0 ? name.slice(0, dot) : name}.jpg`;
}

/** iOS Safari refuses (or blanks) any canvas larger than this many pixels. */
export const MAX_CANVAS_PIXELS = 16_777_216;

/** Scales width × height down, keeping proportions, until it fits in `max` pixels. */
export function capPixels(w: number, h: number, max: number) {
  if (w * h <= max) return { width: w, height: h };
  const scale = Math.sqrt(max / (w * h));
  return { width: Math.max(1, Math.floor(w * scale)), height: Math.max(1, Math.floor(h * scale)) };
}

type Decoded = { source: CanvasImageSource; width: number; height: number; close: () => void };

function fromBitmap(bmp: ImageBitmap): Decoded {
  return { source: bmp, width: bmp.width, height: bmp.height, close: () => bmp.close() };
}

/** Decodes a photo, trying each path a phone might support. All three apply
 *  the EXIF orientation, so sideways photos come out upright. Throws only if
 *  every path fails. */
async function decode(file: File): Promise<Decoded> {
  try {
    return fromBitmap(await createImageBitmap(file, { imageOrientation: "from-image" }));
  } catch {
    // An engine that rejects the option, or a capture too large for it.
  }
  try {
    // Current engines apply the EXIF orientation by default.
    return fromBitmap(await createImageBitmap(file));
  } catch {
    // Fall through to an <img>: Safari decodes HEIC this way.
  }
  const src = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.src = src;
    await img.decode();
    return {
      source: img,
      width: img.naturalWidth,
      height: img.naturalHeight,
      close: () => URL.revokeObjectURL(src),
    };
  } catch (err) {
    URL.revokeObjectURL(src);
    throw err;
  }
}

/** A white canvas of at most width × height, capped to MAX_CANVAS_PIXELS; the
 *  caller draws into the size it gets back. */
function canvasOf(w: number, h: number) {
  const { width, height } = capPixels(w, h, MAX_CANVAS_PIXELS);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d")!;
  // A transparent PNG would come out with a black background in JPEG.
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  return { canvas, ctx, width, height };
}

async function encode(
  file: File,
  draw: (img: Decoded) => HTMLCanvasElement,
): Promise<File | null> {
  // Re-encoding drops every bit of metadata, GPS included.
  const img = await decode(file);
  try {
    const canvas = draw(img);
    const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, "image/jpeg", QUALITY));
    return blob ? new File([blob], jpegName(file.name), { type: "image/jpeg" }) : null;
  } finally {
    img.close();
  }
}

/** 2048 px on the long side, JPEG 0.85. Returns the original whenever it
 *  can't help: not a photo, undecodable here (HEIC on desktop Chrome), any
 *  failure, or a JPEG/PNG/WebP that would come out larger. A HEIC is always
 *  converted — Android can't show HEIC at all. */
export async function shrinkImage(file: File, max = 2048): Promise<File> {
  if (!shouldShrink(file)) return file;
  try {
    const out = await encode(file, (img) => {
      const fit = fitWithin(img.width, img.height, max);
      const { canvas, ctx, width, height } = canvasOf(fit.width, fit.height);
      ctx.drawImage(img.source, 0, 0, width, height);
      return canvas;
    });
    if (!out) return file;
    if (!isHeic(file) && out.size >= file.size) return file;
    return out;
  } catch {
    return file;
  }
}

/** Centre square, size × size, for the profile photo. Returns the original
 *  (not a JPEG) when the photo can't be decoded here. */
export async function squareAvatar(file: File, size = 512): Promise<File> {
  try {
    const out = await encode(file, (img) => {
      const { sx, sy, size: side } = centerSquare(img.width, img.height);
      const target = Math.min(size, side);
      const { canvas, ctx, width, height } = canvasOf(target, target);
      ctx.drawImage(img.source, sx, sy, side, side, 0, 0, width, height);
      return canvas;
    });
    return out ?? file;
  } catch {
    return file;
  }
}

/** One photo at a time: decoding several full-resolution photos at once can
 *  exhaust an iPhone's memory and kill the tab, losing the draft. */
export async function prepareFiles(files: File[]): Promise<File[]> {
  const out: File[] = [];
  for (const f of files) out.push(await shrinkImage(f));
  return out;
}
