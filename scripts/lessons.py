"""Lessons report: patterns across every reviewed slate.

Reads the slate reviews (data/review/) and imported contest results
(data/contests/processed/) and writes:
  data/review/lessons.md      the report (also printed and added to the run summary)
  docs/data/lessons.json      the same, for the bottom of the app's Review tab

Sections:
  1. Ceiling calibration  - how often players beat their ceiling / landed inside
                            floor-ceiling, by salary tier, and a suggested sd_scale
  2. Smash predictors     - smash rate vs the baseline for pre-lock features
  3. Lineup make-up       - what optimal and winning lineups looked like vs our defaults
  4. Ownership            - our estimate vs real %Drafted, and a refit of the
                            ownership weights checked on slates held out of the fit

Rules:
  - No leakage. Only pre-lock features are used to explain results; "was in the
    optimal lineup" and actual points are only ever the thing being measured,
    never an input. Slates whose projections were rebuilt after the fact (the replay
    knew who sat) are skipped unless review.lessons_use_rebuilt_slates is true.
  - Recommendations only. This never edits config/settings.yaml.
  - Below review.min_slates_for_lessons slates, everything is labeled
    "too early to act on".

Usage: python scripts/lessons.py [--include-rebuilt]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import review  # noqa: E402
from pipeline.config import REPO_ROOT, load_settings  # noqa: E402
from pipeline.ownership import WEIGHTS as OWN_WEIGHTS, ownership_features, ownership_from_features  # noqa: E402

LESSONS_MD = review.REVIEW_DIR / "lessons.md"
LESSONS_JSON = review.DOCS_DATA / "lessons.json"
CONTESTS = REPO_ROOT / "data" / "contests" / "processed"

# Pre-lock features: the only columns allowed to explain results.
PRELOCK_FEATURES = ["salary", "positions", "proj", "ceiling", "floor", "sd", "own", "minutes_bump",
                    "team_implied", "team_spread", "game_total", "projected_to_play"]
# Outcomes: what we measure. Never used as inputs.
OUTCOMES = ["actual", "actual_min", "result", "late_scratch", "smash", "in_optimal", "in_top_n", "in_our_lineup"]


# ---------- loading ----------

def _bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(["true", "1", "1.0"])


def load_slates(review_dir: Path, use_rebuilt: bool) -> tuple[list[dict], list[str]]:
    """[{date, doc, players}] for usable slates, and the dates skipped as rebuilt."""
    slates, skipped = [], []
    for f in sorted(review_dir.glob("????-??-??.json")):
        doc = json.loads(f.read_text())
        pcsv = review_dir / f"{doc['gameDate']}_players.csv"
        if not pcsv.exists():
            continue
        if doc["projections"]["source"] != "prelock" and not use_rebuilt:
            skipped.append(doc["gameDate"])
            continue
        p = review.read_csv(pcsv)
        for c in ("projected_to_play", "late_scratch", "smash", "out"):
            if c in p:
                p[c] = _bool(p[c])
        p["date"] = doc["gameDate"]
        slates.append({"date": doc["gameDate"], "doc": doc, "players": p})
    return slates, skipped


def load_contests(date: str, contest_dir: Path | None = None) -> list[dict]:
    folder = (contest_dir or CONTESTS) / date
    return [json.loads(f.read_text()) for f in sorted(folder.glob("*.json"))] if folder.exists() else []


def tier_labels(values: pd.Series, cuts: list) -> pd.Series:
    edges = [-np.inf, *cuts, np.inf]
    labels = [f"under ${cuts[0] / 1000:g}K"] + [f"${a / 1000:g}-{b / 1000:g}K" for a, b in zip(cuts, cuts[1:])] + \
             [f"${cuts[-1] / 1000:g}K+"]
    return pd.cut(values.astype(float), edges, labels=labels, right=False)


def band_labels(values: pd.Series, cuts: list, unit: str = "") -> pd.Series:
    edges = [-np.inf, *cuts, np.inf]
    labels = [f"under {cuts[0]:g}{unit}"] + [f"{a:g}-{b:g}{unit}" for a, b in zip(cuts, cuts[1:])] + \
             [f"{cuts[-1]:g}{unit}+"]
    return pd.cut(values.astype(float), edges, labels=labels, right=False)


def folds_for(dates: list[str], k: int) -> list[tuple[list[str], list[str]]]:
    """Split slates into k groups; each group is held out once (train, test)."""
    k = min(k, len(dates))
    groups = [dates[i::k] for i in range(k)]
    return [([d for d in dates if d not in g], g) for g in groups]


# ---------- 1. ceiling calibration ----------

def calibration(slates: list[dict], cfg: dict, settings: dict) -> dict:
    rows = [s["players"] for s in slates]
    if not rows:
        return {"players": 0}
    df = pd.concat(rows, ignore_index=True)
    d = df[df["projected_to_play"] & (df["result"] == "played") & (df["ceiling"] > df["proj"])].copy()
    if d.empty:
        return {"players": 0}
    target_over, target_in = cfg["lessons_ceiling_target_pct"], cfg["lessons_inside_target_pct"]
    # r = how many "ceiling widths" above the projection he landed (1 = right at the ceiling)
    d["r"] = (d["actual"] - d["proj"]) / (d["ceiling"] - d["proj"])

    def stats(x):
        return {"players": int(len(x)), "overCeilingPct": round(100 * (x["actual"] > x["ceiling"]).mean(), 1),
                "insideRangePct": round(100 * ((x["actual"] >= x["floor"]) & (x["actual"] <= x["ceiling"])).mean(), 1)}

    tiers = [{"tier": str(t), **stats(g)} for t, g in d.groupby(tier_labels(d["salary"], settings["backtest"]["salary_tiers"]), observed=True)]
    # Width multiplier that would put `target_over`% over the ceiling, checked on held-out slates.
    q = 1 - target_over / 100
    held = []
    for train, test in folds_for(sorted(d["date"].unique()), cfg["lessons_holdout_folds"]):
        if not train:
            continue
        k = float(np.quantile(d[d["date"].isin(train)]["r"], q))
        t = d[d["date"].isin(test)]
        held.append((len(t), 100 * (t["r"] > 1).mean(), 100 * (t["r"] > k).mean()))
    k_all = float(np.quantile(d["r"], q))
    cur = settings["projections"]["sd_scale"]
    out = {**stats(d), "targetOverPct": target_over, "targetInsidePct": target_in, "byTier": tiers,
           "widthMultiplier": round(k_all, 3), "sdScaleNow": cur, "sdScaleSuggested": round(cur * k_all, 2)}
    if held:
        n = sum(h[0] for h in held)
        out["heldOut"] = {"slates": len(d["date"].unique()), "overCeilingPctNow": round(sum(h[0] * h[1] for h in held) / n, 1),
                          "overCeilingPctSuggested": round(sum(h[0] * h[2] for h in held) / n, 1)}
    return out


# ---------- 2. smash predictors ----------

def smash_predictors(slates: list[dict], cfg: dict, settings: dict) -> dict:
    if not slates:
        return {"players": 0}
    df = pd.concat([s["players"] for s in slates], ignore_index=True)
    d = df[df["projected_to_play"]].copy()  # pre-lock view: everyone we expected to play
    if d.empty:
        return {"players": 0}
    base = float(d["smash"].mean())
    d["pos1"] = d["positions"].astype(str).str.split("/").str[0]
    groups = {
        "Minutes bump": band_labels(d["minutes_bump"].fillna(0), cfg["lessons_bump_bands"], " min"),
        "Team implied total": band_labels(d["team_implied"], cfg["lessons_implied_bands"]).cat.add_categories("no line").fillna("no line"),
        "Salary": tier_labels(d["salary"], settings["backtest"]["salary_tiers"]),
        "Position": d["pos1"],
    }
    out = {"players": int(len(d)), "baselinePct": round(100 * base, 1), "groups": []}
    for name, labels in groups.items():
        rows = []
        for lab, g in d.groupby(labels, observed=True, sort=True):
            rate = float(g["smash"].mean())
            rows.append({"bucket": str(lab), "players": int(len(g)), "smashPct": round(100 * rate, 1),
                         "lift": round(rate / base, 2) if base else None,
                         "smallSample": bool(len(g) < cfg["lessons_min_bucket_players"])})
        out["groups"].append({"feature": name, "rows": rows})
    return out


# ---------- 3. lineup make-up ----------

def _winner_compositions(slate: dict, cfg: dict) -> list[dict]:
    p = slate["players"]
    by_id = {str(r["dk_id"]): {"salary": int(r["salary"]), "game": r["game"], "team": r["team"],
                               "own": float(r["own"]) if pd.notna(r["own"]) else 0.0,
                               "proj": float(r["proj"]), "actual": float(r["actual"])} for _, r in p.iterrows()}
    totals = {g["game"]: g.get("total") for g in slate["doc"]["games"]}
    out = []
    for c in load_contests(slate["date"]):
        for w in c.get("winningLineups", []):
            ids = [x["id"] for x in (w.get("players") or [])]
            if len(ids) == 8 and all(i in by_id for i in ids):
                out.append(review.composition(ids, by_id, totals, cfg))
    return out


def composition_norms(slates: list[dict], cfg: dict, settings: dict) -> dict:
    opt = [s["doc"]["optimal"]["composition"] for s in slates]
    win = [c for s in slates for c in _winner_compositions(s, cfg)]

    def summary(comps):
        if not comps:
            return None
        flags = [c["maxGameIsHighestTotal"] for c in comps if c["maxGameIsHighestTotal"] is not None]
        return {"lineups": len(comps),
                "avgSalary": round(float(np.mean([c["salary"] for c in comps]))),
                "avgStars": round(float(np.mean([c["stars"] for c in comps])), 2),
                "avgValues": round(float(np.mean([c["values"] for c in comps])), 2),
                "avgMaxFromOneGame": round(float(np.mean([c["maxFromOneGame"] for c in comps])), 2),
                "pctStack3Plus": round(100 * float(np.mean([c["maxFromOneGame"] >= 3 for c in comps])), 1),
                "pctFromHighestTotal": round(100 * float(np.mean(flags)), 1) if flags else None,
                "avgTeamCount": round(float(np.mean([c["teamCount"] for c in comps])), 2),
                "avgOwnSum": round(float(np.mean([c["ownSum"] or 0 for c in comps])), 1)}

    o = settings["optimizer"]
    return {"optimal": summary(opt), "winning": summary(win),
            "defaults": {k: o[k] for k in ("stack_min_players", "stack_top_games", "stack_bring_back",
                                            "gpp_max_exposure_pct", "gpp_ownership_penalty", "gpp_ceiling_weight")}}


# ---------- 4. ownership ----------

def ownership_frames(slates: list[dict]) -> dict[str, pd.DataFrame]:
    """date -> pre-lock features + real ownership (biggest contest that night)."""
    out = {}
    for s in slates:
        cs = load_contests(s["date"])
        if not cs:
            continue
        c = max(cs, key=lambda c: c["fieldSize"])
        real = {o["id"]: o["drafted"] for o in c["ownership"] if o["id"]}
        p = s["players"][["dk_id", "salary", "proj", "minutes_bump", "team_implied", "own", "projected_to_play"]].copy()
        p["dk_id"] = p["dk_id"].astype(str)
        p["out"] = ~p["projected_to_play"]
        p["real"] = p["dk_id"].map(real).fillna(0.0)
        p["minutes_bump"] = p["minutes_bump"].fillna(0.0)
        out[s["date"]] = p[(~p["out"]) | (p["real"] > 0)].reset_index(drop=True)
    return out


def own_error(frames: dict, dates: list[str], cfg: dict, total: float) -> float:
    """Average |estimate - real| over the slates' players (features built once per slate)."""
    errs = []
    for d in dates:
        f = frames[d]
        if "_X" not in f.attrs:
            idx, X = ownership_features(f)
            f.attrs["_X"], f.attrs["_active"] = X, f.index.isin(idx)
        est = np.zeros(len(f))
        est[f.attrs["_active"]] = ownership_from_features(f.attrs["_X"], cfg, total)
        errs.append(np.abs(np.round(est, 1) - f["real"].to_numpy()))
    return float(np.mean(np.concatenate(errs))) if errs else float("nan")


def nelder_mead(fn, x0: np.ndarray, iters: int, step: float = 0.3) -> np.ndarray:
    """Small derivative-free minimizer (no SciPy needed)."""
    n = len(x0)
    pts = [x0.astype(float)] + [x0 + step * np.eye(n)[i] for i in range(n)]
    vals = [fn(p) for p in pts]
    for _ in range(iters):
        order = np.argsort(vals)
        pts, vals = [pts[i] for i in order], [vals[i] for i in order]
        c = np.mean(pts[:-1], axis=0)
        xr = c + (c - pts[-1])
        fr = fn(xr)
        if fr < vals[0]:
            xe = c + 2 * (c - pts[-1])
            fe = fn(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = c + 0.5 * (pts[-1] - c)
            fc = fn(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                pts = [pts[0] + 0.5 * (p - pts[0]) for p in pts]
                vals = [fn(p) for p in pts]
    return pts[int(np.argmin(vals))]


def refit_ownership(frames: dict, dates: list[str], cfg_now: dict, total: float, lcfg: dict) -> dict:
    x0 = np.array([cfg_now[k] for k in OWN_WEIGHTS], dtype=float)
    pen = lcfg["lessons_refit_penalty"]

    def as_cfg(x):
        return {**cfg_now, **{k: float(v) for k, v in zip(OWN_WEIGHTS, x)}}

    def loss(x):  # error on the training slates + a pull back toward today's weights
        return own_error(frames, dates, as_cfg(x), total) + pen * float(np.sum((x - x0) ** 2))

    x = nelder_mead(loss, x0, lcfg["lessons_refit_iterations"])
    return as_cfg(x)


def ownership_lessons(slates: list[dict], cfg: dict, settings: dict) -> dict:
    frames = ownership_frames(slates)
    if not frames:
        return {"slates": 0}
    own_cfg, total = settings["ownership"], settings["projections"]["ownership_total_pct"]
    allf = pd.concat(frames.values(), ignore_index=True)
    allf["err"] = allf["own"].astype(float).fillna(0) - allf["real"]
    tiers = [{"tier": str(t), "players": int(len(g)), "mae": round(float(g["err"].abs().mean()), 2),
              "bias": round(float(g["err"].mean()), 2)}
             for t, g in allf.groupby(tier_labels(allf["salary"], settings["backtest"]["salary_tiers"]), observed=True)]
    out = {"slates": len(frames), "players": int(len(allf)), "mae": round(float(allf["err"].abs().mean()), 2),
           "bias": round(float(allf["err"].mean()), 2), "byTier": tiers}
    dates = sorted(frames)
    if len(dates) < 2:
        out["refit"] = None
        out["refitNote"] = "Needs contest results from at least 2 slates to check a refit on held-out slates."
        return out
    old_err, new_err, n = 0.0, 0.0, 0
    for train, test in folds_for(dates, cfg["lessons_holdout_folds"]):
        fitted = refit_ownership(frames, train, own_cfg, total, cfg)
        m = sum(len(frames[d]) for d in test)
        old_err += own_error(frames, test, own_cfg, total) * m
        new_err += own_error(frames, test, fitted, total) * m
        n += m
    final = refit_ownership(frames, dates, own_cfg, total, cfg)
    out["refit"] = {"heldOutMaeNow": round(old_err / n, 2), "heldOutMaeRefit": round(new_err / n, 2),
                    "weightsNow": {k: own_cfg[k] for k in OWN_WEIGHTS},
                    "weightsRefit": {k: round(final[k], 3) for k in OWN_WEIGHTS}}
    return out


# ---------- recommendations + report ----------

def recommendations(cal: dict, comp: dict, own: dict, cfg: dict) -> list[dict]:
    recs = []
    if cal.get("players") and abs(cal["overCeilingPct"] - cal["targetOverPct"]) > cfg["lessons_ceiling_tolerance_pct"]:
        h = cal.get("heldOut") or {}
        recs.append({"setting": "projections.sd_scale", "title": "Adjust the boom/bust range (sd_scale)",
                     "detail": (f"{cal['overCeilingPct']}% of players beat their ceiling; the target is about "
                                f"{cal['targetOverPct']}%. Changing sd_scale from {cal['sdScaleNow']} to "
                                f"{cal['sdScaleSuggested']} would fix that."
                                + (f" On held-out slates: {h['overCeilingPctNow']}% now vs "
                                   f"{h['overCeilingPctSuggested']}% with the change." if h else "")),
                     "before": f"sd_scale {cal['sdScaleNow']} ({cal['overCeilingPct']}% over ceiling)",
                     "after": f"sd_scale {cal['sdScaleSuggested']}"
                              + (f" ({h['overCeilingPctSuggested']}% over ceiling on held-out slates)" if h else "")})
    win = comp.get("winning") or comp.get("optimal")
    d = comp.get("defaults", {})
    if win and win["pctStack3Plus"] >= cfg["lessons_stack_share_pct"] and d.get("stack_min_players", 0) < 3:
        who = "winning" if comp.get("winning") else "best-possible"
        recs.append({"setting": "optimizer.stack_min_players", "title": "Consider a 3-player game stack in GPPs",
                     "detail": f"{win['pctStack3Plus']}% of {who} lineups had 3+ players from one game "
                               f"({win['lineups']} lineups). Your GPP default doesn't require a stack.",
                     "before": f"stack_min_players {d.get('stack_min_players', 0)}", "after": "stack_min_players 3"})
    r = own.get("refit")
    if r and r["heldOutMaeRefit"] < r["heldOutMaeNow"] - cfg["lessons_min_mae_gain"]:
        changed = {k: (r["weightsNow"][k], r["weightsRefit"][k]) for k in OWN_WEIGHTS
                   if abs(r["weightsNow"][k] - r["weightsRefit"][k]) >= 0.01}
        recs.append({"setting": "ownership.*", "title": "Refit the ownership estimate",
                     "detail": "New weights, tested on slates left out of the fit: "
                               + ", ".join(f"{k} {a:g} → {b:g}" for k, (a, b) in changed.items()),
                     "before": f"held-out ownership miss {r['heldOutMaeNow']} pts",
                     "after": f"{r['heldOutMaeRefit']} pts"})
    return recs


def build(settings: dict, use_rebuilt: bool | None = None, review_dir: Path = review.REVIEW_DIR) -> dict:
    cfg = settings["review"]
    use_rebuilt = cfg["lessons_use_rebuilt_slates"] if use_rebuilt is None else use_rebuilt
    slates, skipped = load_slates(review_dir, use_rebuilt)
    cal = calibration(slates, cfg, settings)
    smash = smash_predictors(slates, cfg, settings)
    comp = composition_norms(slates, cfg, settings)
    own = ownership_lessons(slates, cfg, settings)
    n, need = len(slates), cfg["min_slates_for_lessons"]
    highlights = []
    if skipped:
        highlights.append(f"{len(skipped)} slate(s) skipped because their projections were rebuilt after the fact "
                          f"({', '.join(skipped)}); lessons use pre-lock projections only.")
    if cal.get("players"):
        highlights.append(f"Ceilings: {cal['overCeilingPct']}% of players beat their ceiling (target "
                          f"{cal['targetOverPct']}%); {cal['insideRangePct']}% landed inside floor–ceiling "
                          f"(target {cal['targetInsidePct']}%).")
    if smash.get("players"):
        best = [(g["feature"], r) for g in smash["groups"] for r in g["rows"] if not r["smallSample"] and r["lift"]]
        best.sort(key=lambda x: -x[1]["lift"])
        if best:
            f, r = best[0]
            highlights.append(f"Smash rate is {smash['baselinePct']}% overall; highest for {f.lower()} {r['bucket']} "
                              f"({r['smashPct']}%, {r['players']} players).")
    if own.get("slates"):
        highlights.append(f"Ownership estimate misses real %Drafted by {own['mae']} points on average "
                          f"(bias {own['bias']:+}) over {own['slates']} slate(s).")
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "slates": n, "minSlates": need, "tooEarly": n < need,
        "dates": [s["date"] for s in slates], "skippedRebuilt": skipped,
        "highlights": highlights,
        "recommendations": recommendations(cal, comp, own, cfg),
        "calibration": cal, "smash": smash, "composition": comp, "ownership": own,
        "tables": display_tables(cal, smash, comp, own),
    }


def display_tables(cal, smash, comp, own) -> list[dict]:
    """Small tables for the app."""
    t = []
    if cal.get("byTier"):
        t.append({"title": "Ceiling calibration by salary", "columns": ["Salary", "Players", "Over ceiling", "Inside range"],
                  "rows": [[r["tier"], r["players"], f"{r['overCeilingPct']}%", f"{r['insideRangePct']}%"] for r in cal["byTier"]],
                  "note": f"Targets: about {cal['targetOverPct']}% over ceiling, {cal['targetInsidePct']}% inside floor–ceiling."})
    for g in smash.get("groups", []):
        t.append({"title": f"Smash rate by {g['feature'].lower()}", "columns": ["", "Players", "Smash", "vs avg"],
                  "rows": [[r["bucket"], r["players"], f"{r['smashPct']}%", f"{r['lift']}x" + (" *" if r["smallSample"] else "")]
                           for r in g["rows"]],
                  "note": f"Average smash rate {smash['baselinePct']}%. * = small sample."})
    rows = []
    for label, key in (("Best possible", "optimal"), ("Contest winners", "winning")):
        s = comp.get(key)
        if s:
            rows.append([label, s["lineups"], s["avgStars"], s["avgValues"], f"{s['pctStack3Plus']}%",
                         "–" if s["pctFromHighestTotal"] is None else f"{s['pctFromHighestTotal']}%"])
    if rows:
        t.append({"title": "Lineup make-up", "columns": ["", "Lineups", "Stars", "Values", "3+ one game", "From top total"],
                  "rows": rows, "note": f"Your GPP stack default: {comp['defaults']['stack_min_players'] or 'off'}."})
    if own.get("byTier"):
        t.append({"title": "Ownership estimate vs real", "columns": ["Salary", "Players", "Avg miss", "Bias"],
                  "rows": [[r["tier"], r["players"], r["mae"], f"{r['bias']:+}"] for r in own["byTier"]],
                  "note": "Bias + means we guessed too high."})
    return t


def to_markdown(L: dict) -> str:
    lines = [f"# Lessons across {L['slates']} slate(s)", ""]
    if L["tooEarly"]:
        lines += [f"**Too early to act on:** {L['slates']} of {L['minSlates']} slates so far. "
                  "Numbers are shown for interest only.", ""]
    lines += [f"- {h}" for h in L["highlights"]] + [""]
    lines += ["## Recommended changes", ""]
    if L["recommendations"]:
        for r in L["recommendations"]:
            lines += [f"### {r['title']}", "", r["detail"], "", f"- Before: {r['before']}", f"- After: {r['after']}",
                      f"- Setting: `{r['setting']}`", ""]
    else:
        lines += ["None yet.", ""]
    for t in L["tables"]:
        lines += [f"## {t['title']}", "", "| " + " | ".join(map(str, t["columns"])) + " |",
                  "|" + "---|" * len(t["columns"])]
        lines += ["| " + " | ".join(map(str, r)) + " |" for r in t["rows"]]
        lines += ["", t.get("note", ""), ""]
    lines += ["_Recommendations only. Nothing in config/settings.yaml is changed until Chris approves it._"]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lessons across all reviewed slates (recommendations only).")
    ap.add_argument("--include-rebuilt", action="store_true",
                    help="also use slates whose projections were rebuilt after the fact (preview only; not written)")
    args = ap.parse_args(argv)
    settings = load_settings()
    L = build(settings, use_rebuilt=True if args.include_rebuilt else None)
    md = to_markdown(L)
    print(md)
    if args.include_rebuilt:
        print("(preview with rebuilt slates: nothing written)")
        return 0
    LESSONS_MD.parent.mkdir(parents=True, exist_ok=True)
    LESSONS_MD.write_text(md, encoding="utf-8")
    LESSONS_JSON.parent.mkdir(parents=True, exist_ok=True)
    LESSONS_JSON.write_text(json.dumps(L, indent=1), encoding="utf-8")
    review.write_index()  # tells the app a lessons file exists
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
