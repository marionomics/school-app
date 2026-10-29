import { describe, expect, it } from "vitest";
import {
  activeMention,
  insertMention,
  liveTeam,
  parseUsernames,
  splitMentions,
  MENTION_SOURCE,
} from "./mentions";
import type { Author, Mention } from "./types";

const ana: Author = { id: 1, username: "ana", name: "Ana", avatar_url: null, role: "student" };
const m = (user: Author, kind: "social" | "team" = "social", removed = false): Mention => ({
  user, kind, removed,
});

describe("parseUsernames", () => {
  it("mirrors the server: ordered, unique, lowercase", () => {
    expect(parseUsernames("con @Ana y @pedro_2, otra vez @ana")).toEqual(["ana", "pedro_2"]);
  });
  it("ignores emails, short and glued @", () => {
    expect(parseUsernames("pedro@gmail.com @ab a@pedro hola@@x")).toEqual([]);
  });
});

describe("splitMentions", () => {
  it("links only mentions the server resolved", () => {
    expect(splitMentions("hola @Ana y @nadie", [m(ana)])).toEqual([
      { text: "hola " },
      { mention: ana },
      { text: " y @nadie" },
    ]);
  });
  it("is plain text without mentions", () => {
    expect(splitMentions("pedro@gmail.com")).toEqual([{ text: "pedro@gmail.com" }]);
  });
});

describe("activeMention", () => {
  it("finds the @word under the caret", () => {
    expect(activeMention("hola @an", 8)).toEqual({ start: 5, query: "an" });
  });
  it("needs at least one letter, and not inside an email", () => {
    expect(activeMention("hola @", 6)).toBeNull();
    expect(activeMention("pedro@gm", 8)).toBeNull();
  });
});

describe("insertMention", () => {
  it("replaces the partial word and adds a space", () => {
    expect(insertMention("hola @an qué", 5, 8, "ana")).toEqual({
      value: "hola @ana  qué",
      caret: 10,
    });
  });
});

describe("liveTeam", () => {
  it("lists team mentions not removed", () => {
    const luis = { ...ana, id: 2, username: "luis" };
    const eva = { ...ana, id: 3, username: "eva" };
    expect(liveTeam({ mentions: [m(ana, "team"), m(luis, "team", true), m(eva)] })).toEqual([ana]);
  });
});

it("uses no regex lookbehind (old iOS Safari throws on it)", () => {
  expect(MENTION_SOURCE).not.toContain("(?<");
});
