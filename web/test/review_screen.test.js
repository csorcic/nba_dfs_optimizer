// Review screen HTML (no browser needed).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { reviewHtml, lessonsHtml } from "../app/review.js";

const doc = JSON.parse(readFileSync(new URL("../../docs/data/review_2026-11-07.json", import.meta.url), "utf8"));
const index = { dates: [{ date: "2026-11-07", pctOfOptimal: doc.standing.pctOfOptimal }] };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const f = {
  esc,
  money: (n) => `$${n}`,
  pts: (n) => (n === null || n === undefined ? "–" : Number(n).toFixed(1)),
  dayLabel: (d) => d,
};

test("review screen shows the optimum, our lineup, smash list and make-up", () => {
  const html = reviewHtml({ index, doc, lessons: null, error: null }, f);
  assert.ok(html.includes("Best possible lineup"));
  assert.ok(html.includes(doc.standing.optimalActual.toFixed(1)));
  for (const p of doc.optimal.players) assert.ok(html.includes(esc(p.name)), p.name);
  for (const p of doc.ours.players) assert.ok(html.includes(esc(p.name)), p.name);
  for (const s of doc.smash) assert.ok(html.includes(esc(s.name)), s.name);
  assert.ok(html.includes("Lineup make-up"));
  assert.ok(html.includes("Rebuilt projections")); // the Nov 7 review had no pre-lock snapshot
  assert.ok(html.includes('<option value="2026-11-07" selected>'));
  assert.ok(!html.includes("<h2>Contests</h2>")); // no standings imported yet
});

test("contest results appear once standings exist", () => {
  const withContest = {
    ...doc,
    contests: [{ name: "NBA $5 Double Up", fieldSize: 2000, winningScore: 377.5, top1Score: 340, cashLine: 280.25,
      mine: { best: { points: 301, rank: 400, percentile: 80 } } }],
  };
  const html = reviewHtml({ index, doc: withContest, error: null }, f);
  assert.ok(html.includes("<h2>Contests</h2>"));
  assert.ok(html.includes("377.5"));
  assert.ok(html.includes("280.3"));
  assert.ok(html.includes("rank 400"));
  assert.ok(html.includes("beat 80% of the field"));
});

test("empty and error states", () => {
  assert.ok(reviewHtml({ index: null, doc: null, error: "none" }, f).includes("No slate reviews yet"));
  assert.ok(reviewHtml({ index: null, doc: null, error: "HTTP 500" }, f).includes("Couldn't load"));
  assert.ok(reviewHtml({ index: null, doc: null, error: null, loading: true }, f).includes("Loading"));
});

test("lessons are labeled too early below the slate threshold", () => {
  const html = lessonsHtml({ slates: 3, minSlates: 20, tooEarly: true, highlights: ["x"], recommendations: [] }, f);
  assert.ok(html.includes("Too early to act on"));
  assert.ok(html.includes("Nothing changes until you approve"));
});

test("real Nov 9 review shows the contest, my finish and real ownership", () => {
  const d9 = JSON.parse(readFileSync(new URL("../../docs/data/review_2026-11-09.json", import.meta.url), "utf8"));
  const html = reviewHtml({ index, doc: d9, error: null }, f);
  const c = d9.contests[0];
  assert.ok(html.includes("<h2>Contests</h2>"));
  assert.ok(html.includes(c.winningScore.toFixed(1)));
  assert.ok(html.includes(`rank ${c.mine.best.rank}`));
  assert.ok(html.includes("Real ownership vs our estimate"));
  assert.ok(html.includes(esc(d9.ownershipCheck.list[0].name)));
});
