import { describe, expect, it } from "vitest";
import { canSubmit, capFiles, MAX_FILES } from "./attachments";

const file = (name: string) => new File(["x"], name, { type: "application/pdf" });

describe("capFiles", () => {
  it("returns an empty array when nothing was chosen", () => {
    expect(capFiles(null)).toEqual([]);
    expect(capFiles(undefined)).toEqual([]);
  });

  it("keeps every file up to the cap", () => {
    const picked = [file("a.pdf"), file("b.pdf")];
    expect(capFiles(picked).map((f) => f.name)).toEqual(["a.pdf", "b.pdf"]);
  });

  it("drops everything past the fourth", () => {
    const picked = ["a", "b", "c", "d", "e"].map((n) => file(`${n}.pdf`));
    expect(capFiles(picked)).toHaveLength(MAX_FILES);
    expect(capFiles(picked).map((f) => f.name)).toEqual([
      "a.pdf",
      "b.pdf",
      "c.pdf",
      "d.pdf",
    ]);
  });
});

describe("canSubmit", () => {
  it("is false with neither text nor files", () => {
    expect(canSubmit("", [])).toBe(false);
  });

  it("is false when the text is only whitespace", () => {
    expect(canSubmit("   \n ", [])).toBe(false);
  });

  it("is true with text alone", () => {
    expect(canSubmit("aquí está mi entrega", [])).toBe(true);
  });

  it("is true with a file and no text — a photo IS the entrega", () => {
    expect(canSubmit("", [file("foto.jpg")])).toBe(true);
  });

  it("is true with both", () => {
    expect(canSubmit("ahí va", [file("foto.jpg")])).toBe(true);
  });
});
