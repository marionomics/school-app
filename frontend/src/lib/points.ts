/** Points are always on the 0–100 scale. One point on that scale is one
 *  décima, which is 0.1 on the 10-scale students and teachers actually talk
 *  about. Every surface that shows a points value goes through here — getting
 *  this wrong by a factor of ten is the single most expensive UI mistake
 *  available in this app.
 *
 *  Takes a magnitude: a falta is passed as 10 or -10 and reads the same either
 *  way, because the minus belongs to the label next to it, not to the units.
 *
 *  Copy here is a placeholder. Mario writes the final wording. */
export function formatPoints(points: number): string {
  const n = Math.abs(points);
  if (n === 0) return "0 puntos";

  const puntos = `${n} ${n === 1 ? "punto" : "puntos"}`;
  const decimas =
    n === 0.5 ? "media décima" : n === 1 ? "1 décima" : `${n} décimas`;

  // Only worth spelling out on the 10-scale when it lands somewhere clean —
  // "0.3 puntos de 10" helps nobody.
  const onTen = n / 10;
  const escala10 =
    onTen === 0.5
      ? " · medio punto de 10"
      : onTen === 1
        ? " · un punto entero de 10"
        : Number.isInteger(onTen) && onTen > 1
          ? ` · ${onTen} puntos enteros de 10`
          : "";

  return `${puntos} · ${decimas}${escala10}`;
}

/** Mirrors like_points() in backend/app/services/grades.py: the nth like is
 *  worth n^exponent − (n−1)^exponent, so the total for n likes is n^exponent.
 *  Shown to the teacher so a curve is chosen by its consequence rather than by
 *  its exponent. Assumes like_value 1.0, which is what the preview means. */
export function likeCurvePreview(exponent: number, n = 100): number {
  return Math.round(Math.pow(n, exponent));
}
