import { describe, expect, it } from "vitest";
import { photoLayout, splitAttachments } from "./photos";
import type { Attachment } from "./types";

const att = (id: number, url: string | null, mime = "image/jpeg"): Attachment =>
  ({ id, file_name: `f${id}`, mime_type: mime, url }) as Attachment;

describe("photoLayout", () => {
  it("one photo is a single box, two to four a grid, none is none", () => {
    expect(photoLayout(0)).toBe("none");
    expect(photoLayout(1)).toBe("single");
    expect(photoLayout(2)).toBe("grid");
    expect(photoLayout(4)).toBe("grid");
  });
});

describe("splitAttachments", () => {
  it("anything with a url is a photo; the rest stay files, order kept", () => {
    const { photos, files } = splitAttachments([
      att(1, "u1"), att(2, null, "application/pdf"), att(3, null, "image/heic"), att(4, "u4"),
    ]);
    expect(photos.map((a) => a.id)).toEqual([1, 4]);
    expect(files.map((a) => a.id)).toEqual([2, 3]);
  });
});
