#!/usr/bin/env python3
"""Write surface/surface.json: the recommended model's win probability on a grid, for bilinear lookup.

    nice -n 19 python3 logs/loss-analysis/surface/export.py "MODEL PREFIX"   (or "flex")

Grid nodes every 100 cp from -3000 to +3000 for ordinary (non-mate) scores, plus separate entries for a forced mate
for / against on either board (mates are categories, not a score).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa
from common import HERE, sigmoid  # noqa
from models import SIMPLE

AX = list(range(-3000, 3001, 100))


def main():
    nm = sys.argv[1]
    pairs = json.load(open(os.path.join(HERE, "pairs.json")))
    G = len({(p["m"], p["g"]) for p in pairs})
    if nm == "flex":
        ff = json.load(open(os.path.join(HERE, "flex_full.json")))
        P = lambda a, b, fa=0, fb=0: sigmoid(C.flex_eval(ff["theta"], a, b, fa, fb))
        desc = {"model": "flexible symmetric surface (bilinear on knots, mates as categories)", "lambda": ff["lam"],
                "knots": ff["knots"]}
    else:
        name, feat, haspow = [m for m in SIMPLE if m[0].startswith(nm)][0]
        s = json.load(open(os.path.join(HERE, "cv_simple.json")))[name]
        beta, p = s["beta"], s["p"]
        P = lambda a, b, fa=0, fb=0: sigmoid(sum(u * v for u, v in zip(beta, feat(a / 1000, b / 1000, p, fa, fb))))
        desc = {"model": name, "beta": beta, "p_or_L_in_1000cp": p, "units": "scores in 1000 cp inside the formula"}
        if name.startswith("m1."):
            k = 1000 / beta[1]
            desc["integer_form"] = {"scale_cp_per_logit": round(k, 1), "mate_for_extra_cp": round(beta[2] * k),
                                    "mate_against_extra_cp": round(-beta[3] * k), "offset_cp": round(-beta[0] * k)}
            print("integer form:", desc["integer_form"])
    grid = [[round(P(a, b), 5) for b in AX] for a in AX]
    out = {
        "what": "Team win probability. p[i][j]: own board score AX[i], partner board score AX[j], both centipawns from "
                "each seat's own point of view, ordinary (non-mate) scores clamped to +/-3000; bilinear interpolation "
                "between nodes. A forced mate on a board is NOT a score here: use the mate_* vectors (indexed by the "
                "other board's score) or mate_both. "
                f"Fitted on {G} games / {len(pairs)} paired decisions between HypeBeast builds with HBFeedPrices=false; "
                "descriptive (how such games ended), not causal.",
        "axis_cp": AX, "own_axis": "rows (i)", "partner_axis": "columns (j)", "p": grid,
        "mate_for_vs_other": [round(P(3000, b, 1, 0), 5) for b in AX],
        "mate_against_vs_other": [round(P(-3000, b, -1, 0), 5) for b in AX],
        "mate_both": {"for_for": round(P(3000, 3000, 1, 1), 5), "for_against": round(P(3000, -3000, 1, -1), 5),
                      "against_against": round(P(-3000, -3000, -1, -1), 5)},
        "source": desc,
    }
    json.dump(out, open(os.path.join(HERE, "surface.json"), "w"))
    i0 = AX.index(0)
    print("wrote surface.json", len(AX), "x", len(AX), "P(0,0)=", grid[i0][i0], "P(0,600)=", grid[i0][i0 + 6],
          "P(300,300)=", grid[i0 + 3][i0 + 3], "mate for vs 0:", out["mate_for_vs_other"][i0],
          "mate against vs 0:", out["mate_against_vs_other"][i0], out["mate_both"])


if __name__ == "__main__":
    main()
