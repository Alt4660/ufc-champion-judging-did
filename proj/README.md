# Do UFC judges favor the champion?

ECON 5200 Final Project, Milestone 1: Proposal + EDA.

**Question.** Does holding a UFC title cause judges to score a fighter's decisions more favorably, holding in-fight
performance fixed? Design: staggered difference-in-differences at the fighter-fight level.

## Reproduce

```bash
pip install pandas numpy statsmodels matplotlib jupyter
python scripts/build_table.py          # builds data/processed/fighter_fights.csv and sample_funnel.json
jupyter nbconvert --to notebook --execute --inplace ufc_champion_eda.ipynb
```

In Colab, upload the repo (or clone it) and open `ufc_champion_eda.ipynb`. If you run it without the repo files, edit
`BASE` in the "Load the data" cell to this repo's raw GitHub URL.

## Data

| File in `data/raw/` | Source | Used for |
|---|---|---|
| `ufc_event_details.csv`, `ufc_fight_results.csv` | Public scrape of ufcstats.com: https://github.com/Greco1899/scrape_ufc_stats | winner, decision type, event date, title bouts |
| `kaggle_master.csv` | Kaggle, "UFC Datasets 1994-2026" by neelagiriaditya (`master.csv`): https://www.kaggle.com/datasets/neelagiriaditya/ufc-datasets-1994-2025 | fight totals: strikes, takedowns, control time, knockdowns, fighter birth dates |

Scorecards in the results file are sorted low-high on every card, so they carry margins but not direction. Judge votes
for a fighter are rebuilt from the winner and the decision type: unanimous win 3-0, split win 2-1, majority win 2-0-1.

The champion in each title bout is the winner of the previous undisputed title bout in the same division, if they
appear in the bout. Interim and tournament-final title bouts are not treated as champion fights. Derived title winners
were checked against Wikipedia's List of UFC champions (107 of 109 names matched; the other two are spelling
differences).

## Layout

```
scripts/build_table.py      merges the two sources, derives champions and judge votes
ufc_champion_eda.ipynb      Part 2 of the course starter notebook
data/raw/                   source files, unmodified
data/processed/             fighter_fights.csv, title_wins.csv, sample_funnel.json
figures/figure1.png         Figure 1 of the proposal
```
