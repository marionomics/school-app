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

async function encode(
  file: File,
  draw: (bmp: ImageBitmap) => { canvas: HTMLCanvasElement },
): Promise<File | null> {
  // "from-image" applies the EXIF orientation, so sideways photos come out
  // upright. Re-encoding also drops every bit of metadata, GPS included.
  const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
  try {
    const { canvas } = draw(bmp);
    const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, "image/jpeg", QUALITY));
    return blob ? new File([blob], jpegName(file.name), { type: "image/jpeg" }) : null;
  } finally {
    bmp.close();
  }
}

function canvasOf(width: number, height: number) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d")!;
  // A transparent PNG would come out with a black background in JPEG.
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  return { canvas, ctx };
}

/** 2048 px on the long side, JPEG 0.85. Returns the original whenever it
 *  can't help: not a photo, undecodable here (HEIC on desktop Chrome), any
 *  failure, or a JPEG/PNG/WebP that would come out larger. A HEIC is always
 *  converted — Android can't show HEIC at all. */
export async function shrinkImage(file: File, max = 2048): Promise<File> {
  if (!shouldShrink(file)) return file;
  try {
    const out = await encode(file, (bmp) => {
      const { width, height } = fitWithin(bmp.width, bmp.height, max);
      const { canvas, ctx } = canvasOf(width, height);
      ctx.drawImage(bmp, 0, 0, width, height);
      return { canvas };
    });
    if (!out) return file;
    if (!isHeic(file) && out.size >= file.size) return file;
    return out;
  } catch {
    return file;
  }
}

/** Centre square, size × size, for the profile photo. */
export async function squareAvatar(file: File, size = 512): Promise<File> {
  try {
    const out = await encode(file, (bmp) => {
      const { sx, sy, size: side } = centerSquare(bmp.width, bmp.height);
      const target = Math.min(size, side);
      const { canvas, ctx } = canvasOf(target, target);
      ctx.drawImage(bmp, sx, sy, side, side, 0, 0, target, target);
      return { canvas };
    });
    return out ?? file;
  } catch {
    return file;
  }
}

export function prepareFiles(files: File[]): Promise<File[]> {
  return Promise.all(files.map((f) => shrinkImage(f)));
}
