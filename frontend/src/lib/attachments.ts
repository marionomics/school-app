// The server enforces the same cap (MAX_FILES in backend/app/routers/posts.py);
// this exists so the UI never offers to send a fifth file it knows is refused.
export const MAX_FILES = 4;

/**
 * Each pick ADDS to the selection. A handwritten tarea is often several photos
 * taken one at a time, and replacing the list would silently drop the earlier
 * pages. Anything past the cap is dropped.
 */
export function addFiles(
  existing: File[],
  picked: FileList | File[] | null | undefined,
): File[] {
  return [...existing, ...Array.from(picked ?? [])].slice(0, MAX_FILES);
}

/**
 * A post is publishable with text, with files, or with both — never with
 * neither. Matches `create_post`, which accepts an empty body when files are
 * present: requiring a caption on a photo of handwritten work is busywork.
 */
export function canSubmit(text: string, files: File[]): boolean {
  return text.trim().length > 0 || files.length > 0;
}
