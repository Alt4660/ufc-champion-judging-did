"""Build the fighter-fight analysis table for: do judges favor UFC champions?

Inputs (data/raw):
  ufc_event_details.csv, ufc_fight_results.csv  - community scrape of ufcstats.com
        (github.com/Greco1899/scrape_ufc_stats): method, scorecards, event date.
  kaggle_master.csv - Kaggle UFC dataset (fight totals: strikes, takedowns, control time).

Output: data/processed/fighter_fights.csv  (two rows per decision fight, one per fighter)

Run from the repo root:  python scripts/build_table.py
"""
import re
import unicodedata
from pathlib import Path

import pandas as pd

RAW = Path("data/raw")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


# ---------------------------------------------------------------- results file
ev = pd.read_csv(RAW / "ufc_event_details.csv")
fr = pd.read_csv(RAW / "ufc_fight_results.csv")
ev["EVENT"] = ev["EVENT"].str.strip()
fr["EVENT"] = fr["EVENT"].str.strip()
for c in ["METHOD", "WEIGHTCLASS", "DETAILS", "BOUT", "OUTCOME"]:
    fr[c] = fr[c].fillna("").astype(str).str.strip()
ev["date"] = pd.to_datetime(ev["DATE"], errors="coerce")
fr = fr.merge(ev[["EVENT", "date", "LOCATION"]], on="EVENT", how="left")
fr["file_order"] = range(len(fr))  # file is newest-first; used to break same-day ties

names = fr["BOUT"].str.split(" vs. ", n=1, expand=True)
fr["f1"], fr["f2"] = names[0].str.strip(), names[1].str.strip()
fr["f1_won"] = fr["OUTCOME"].str.startswith("W")
fr["f2_won"] = fr["OUTCOME"].str.startswith("L")
fr["winner"] = fr["f1"].where(fr["f1_won"], fr["f2"].where(fr["f2_won"]))

# ------------------------------------------------- champion in each title bout
# Real UFC title bouts only (drops TUF / Road to UFC tournament finals, which have no champion).
title_re = r"^UFC (Interim )?(Women's )?[A-Za-z ]+ Title Bout$"
tb = fr[fr["WEIGHTCLASS"].str.match(title_re)].copy()
tb["interim"] = tb["WEIGHTCLASS"].str.contains("Interim")
tb["division"] = (tb["WEIGHTCLASS"].str.replace(r"^UFC (Interim )?", "", regex=True)
                  .str.replace(" Title Bout", "", regex=False))
champ_of_fight = {}
title_win_date = {}  # fighter -> date of first undisputed-title win
for div, g in tb[~tb["interim"]].groupby("division"):
    g = g.sort_values(["date", "file_order"], ascending=[True, False])
    champ = None
    for idx, r in g.iterrows():
        incumbent = champ if champ in (r["f1"], r["f2"]) else None
        champ_of_fight[idx] = incumbent
        if pd.notna(r["winner"]):
            champ = r["winner"]
            if incumbent != r["winner"]:  # won the belt in this fight
                title_win_date.setdefault(r["winner"], r["date"])
        elif incumbent:
            champ = incumbent
pd.DataFrame({"fighter": list(title_win_date), "first_title_win": list(title_win_date.values())}).to_csv(
    OUT / "title_wins.csv", index=False)
fr["incumbent_champ"] = pd.Series(champ_of_fight)
fr["is_title"] = fr.index.isin(tb[~tb["interim"]].index)
fr["is_interim_title"] = fr.index.isin(tb[tb["interim"]].index)

# ------------------------------------------------------------- judge votes
# Scorecards in DETAILS are sorted low-high on every card, so they carry margins, not direction.
# Votes for a fighter are rebuilt from the winner and the method:
#   unanimous win 3-0, split win 2-1, majority win 2 (third judge scored a draw).
dec = fr[fr["METHOD"].str.startswith("Decision")].copy()
dec = dec[dec["winner"].notna()]  # drops draws / no contests
dec["method_short"] = dec["METHOD"].str.replace("Decision - ", "", regex=False)
votes_winner = {"Unanimous": 3, "Split": 2, "Majority": 2}
votes_loser = {"Unanimous": 0, "Split": 1, "Majority": 0}
pat = re.compile(r"(\d{2}) - (\d{2})")
dec["card_margins"] = dec["DETAILS"].apply(lambda s: [abs(int(a) - int(b)) for a, b in pat.findall(s)])

# --------------------------------------------------------- Kaggle performance
m = pd.read_csv(RAW / "kaggle_master.csv", low_memory=False)
m["date"] = pd.to_datetime(m["event_date"], errors="coerce")
m["key"] = m.apply(lambda r: (r["date"], frozenset((norm(r["r_fighter_name"]), norm(r["b_fighter_name"])))), axis=1)
dec["key"] = dec.apply(lambda r: (r["date"], frozenset((norm(r["f1"]), norm(r["f2"])))), axis=1)
perf_cols = ["total_sig_landed", "total_td_success", "total_ctrl_seconds", "total_kd", "total_sub_att"]
keep = ["key", "r_fighter_name", "b_fighter_name", "r_dob", "b_dob", "r_reach_inches", "b_reach_inches",
        "rounds_fought", "time_format"] + [f"{s}_{c}" for s in "rb" for c in perf_cols]
mm = m[keep].drop_duplicates("key")
d = dec.merge(mm, on="key", how="left", suffixes=("", "_k"))
print(f"decisions with a winner: {len(d)}; matched to Kaggle performance: {d['r_fighter_name'].notna().sum()}")
import json
funnel = {
    "ufc_events": int(len(ev)),
    "ufc_fights": int(len(fr)),
    "decisions_all": int(fr["METHOD"].str.startswith("Decision").sum()),
    "decisions_with_winner": int(len(dec)),
    "decisions_matched_to_performance": int(d["r_fighter_name"].notna().sum()),
    "title_bouts_undisputed": int(fr["is_title"].sum()),
    "title_bouts_interim": int(fr["is_interim_title"].sum()),
    "title_bouts_with_incumbent": int(fr.loc[fr["is_title"], "incumbent_champ"].notna().sum()),
    "first_date": str(fr["date"].min().date()), "last_date": str(fr["date"].max().date()),
}
with open(OUT / "sample_funnel.json", "w") as fh:
    json.dump(funnel, fh, indent=1)

# -------------------------------------------------- long table: one row/fighter
rows = []
for _, r in d.iterrows():
    for side in ("f1", "f2"):
        me, opp = (r["f1"], r["f2"]) if side == "f1" else (r["f2"], r["f1"])
        won = r["winner"] == me
        rec = {
            "fight_url": r["URL"], "date": r["date"], "event": r["EVENT"], "location": r["LOCATION"],
            "weightclass": r["WEIGHTCLASS"], "fighter": me, "opponent": opp, "won": int(won),
            "method": r["method_short"], "scheduled": r["TIME FORMAT"],
            "votes": (votes_winner if won else votes_loser)[r["method_short"]],
            "is_title": r["is_title"], "is_interim_title": r["is_interim_title"],
            "incumbent_champ": r["incumbent_champ"],
            "i_am_champ": int(r["incumbent_champ"] == me) if pd.notna(r["incumbent_champ"]) else 0,
            "opp_is_champ": int(r["incumbent_champ"] == opp) if pd.notna(r["incumbent_champ"]) else 0,
            "min_card_margin": min(r["card_margins"]) if r["card_margins"] else None,
        }
        if pd.notna(r["r_fighter_name"]):
            kr = norm(r["r_fighter_name"]) == norm(me)  # is `me` the Kaggle red corner?
            a, b = ("r", "b") if kr else ("b", "r")
            for c in perf_cols:
                rec[f"d_{c}"] = r[f"{a}_{c}"] - r[f"{b}_{c}"]
            rec["rounds_fought"] = r["rounds_fought"]
            rec["dob"] = r[f"{a}_dob"]
            rec["reach_in"] = r[f"{a}_reach_inches"]
        rows.append(rec)
ff = pd.DataFrame(rows)
ff["vote_share"] = ff["votes"] / 3
ff["title_win_date"] = ff["fighter"].map(title_win_date)
ff["ever_champ"] = ff["title_win_date"].notna().astype(int)
ff["post_title"] = ((ff["ever_champ"] == 1) & (ff["date"] > ff["title_win_date"])).astype(int)
ff["age"] = (ff["date"] - pd.to_datetime(ff["dob"], errors="coerce")).dt.days / 365.25
ff.to_csv(OUT / "fighter_fights.csv", index=False)
print(ff.shape, "| treated fighters (ever champ, with decisions):", ff.loc[ff.ever_champ == 1, "fighter"].nunique())
