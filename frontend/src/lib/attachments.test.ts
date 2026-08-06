import { describe, expect, it } from "vitest";
import { addFiles, canSubmit, MAX_FILES } from "./attachments";

const file = (name: string) => new File(["x"], name, { type: "application/pdf" });

describe("addFiles", () => {
  it("returns the existing list unchanged when nothing was picked", () => {
    const existing = [file("a.pdf")];
    expect(addFiles(existing, null)).toEqual(existing);
    expect(addFiles(existing, undefined)).toEqual(existing);
  });

  it("appends the newly picked files to the existing selection", () => {
    const existing = [file("a.pdf")];
    const picked = [file("b.pdf")];
    expect(addFiles(existing, picked).map((f) => f.name)).toEqual(["a.pdf", "b.pdf"]);
  });

  it("drops everything past the cap, keeping the earliest files", () => {
    const existing = [file("a.pdf"), file("b.pdf"), file("c.pdf")];
    const picked = [file("d.pdf"), file("e.pdf")];
    const result = addFiles(existing, picked);
    expect(result).toHaveLength(MAX_FILES);
    expect(result.map((f) => f.name)).toEqual(["a.pdf", "b.pdf", "c.pdf", "d.pdf"]);
  });

  it("preserves order: existing files first, then picked files", () => {
    const existing = [file("first.pdf")];
    const picked = [file("second.pdf"), file("third.pdf")];
    expect(addFiles(existing, picked).map((f) => f.name)).toEqual([
      "first.pdf",
      "second.pdf",
      "third.pdf",
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
