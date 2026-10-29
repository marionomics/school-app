import { describe, expect, it } from "vitest";
import { teamResultToast, teamWarning } from "./teamWarnings";
import type { Post } from "./types";

describe("teamWarning", () => {
  it("is null when the mention joins", () => {
    expect(teamWarning({ username: "ana", status: "ok", team_author: null })).toBeNull();
  });
  it("names the team someone is already on", () => {
    expect(
      teamWarning({ username: "pedro", status: "on_team", team_author: "ana" }),
    ).toBe("@pedro ya entregó con el equipo de @ana");
  });
  it("says nothing about a self-mention", () => {
    expect(teamWarning({ username: "yo", status: "self", team_author: null })).toBeNull();
  });
});

describe("teamResultToast", () => {
  const sent = (team: string[]) =>
    ({
      mentions: team.map((u, i) => ({
        user: { id: i, username: u, name: u, avatar_url: null, role: "student" },
        kind: "team",
        removed: false,
      })),
    }) as unknown as Post;
  it("is silent when publish matched the check", () => {
    expect(teamResultToast(["ana"], sent(["ana"]))).toBeNull();
  });
  it("says who ended up on the team when it changed", () => {
    expect(teamResultToast(["ana", "luis"], sent(["ana"]))).toBe("Equipo: @ana");
  });
  it("says when nobody did", () => {
    expect(teamResultToast(["ana"], sent([]))).toBe("Entregaste sin equipo");
  });
});
