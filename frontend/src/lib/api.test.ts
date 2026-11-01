import { describe, expect, it } from "vitest";
import { detailMessage } from "./api";

describe("detailMessage", () => {
  it("keeps string details", () => {
    expect(detailMessage("No encontrado")).toBe("No encontrado");
  });
  it("takes the first Pydantic message without its prefix", () => {
    expect(detailMessage([{ msg: "Value error, Niveles en orden" }, { msg: "otro" }])).toBe(
      "Niveles en orden",
    );
  });
  it("returns null for anything else", () => {
    expect(detailMessage([])).toBeNull();
    expect(detailMessage(undefined)).toBeNull();
  });
});
