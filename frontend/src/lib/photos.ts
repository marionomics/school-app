import type { Attachment } from "./types";

/** One photo gets a fixed 4:5 box (whole photo visible, no jump while
 *  loading); two to four get a two-column grid of square tiles. */
export function photoLayout(n: number): "single" | "grid" | "none" {
  if (n <= 0) return "none";
  return n === 1 ? "single" : "grid";
}

/** The server decides what is displayable by sending a url. A HEIC or a PDF
 *  arrives with url = null and stays a chip. */
export function splitAttachments(atts: Attachment[]) {
  return {
    photos: atts.filter((a) => a.url),
    files: atts.filter((a) => !a.url),
  };
}
