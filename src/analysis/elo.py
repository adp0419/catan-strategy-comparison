import math
import random

ELO_SCALE = 400
PRIOR_GAMES = 1.0
ITERATIONS = 2000
TOL = 1e-10
BOOTSTRAPS = 200


def fit_strengths(names, wins, prior=PRIOR_GAMES):
    w = {(a, b): wins.get((a, b), 0) + prior / 2 for a in names for b in names if a != b and ((a, b) in wins or (b, a) in wins)}
    s = {n: 1.0 for n in names}
    for _ in range(ITERATIONS):
        new = {}
        for i in names:
            won = sum(v for (a, _), v in w.items() if a == i)
            denom = sum((w[(i, j)] + w[(j, i)]) / (s[i] + s[j]) for (a, j) in w if a == i)
            new[i] = won / denom if denom else s[i]
        norm = math.exp(sum(math.log(v) for v in new.values()) / len(new))
        new = {k: v / norm for k, v in new.items()}
        done = max(abs(new[k] - s[k]) for k in names) < TOL
        s = new
        if done:
            break
    return s


def to_elo(strengths, anchor=None):
    elo = {k: ELO_SCALE * math.log10(v) for k, v in strengths.items()}
    shift = elo[anchor] if anchor in elo else sum(elo.values()) / len(elo)
    return {k: v - shift for k, v in elo.items()}


def bootstrap(names, wins, anchor=None, n=BOOTSTRAPS, seed=0):
    rng = random.Random(seed)
    pairs = {tuple(sorted(k)) for k in wins}
    samples = {k: [] for k in names}
    for _ in range(n):
        resampled = {}
        for a, b in pairs:
            games = wins.get((a, b), 0) + wins.get((b, a), 0)
            p = wins.get((a, b), 0) / games if games else 0.5
            won = sum(rng.random() < p for _ in range(games))
            resampled[(a, b)] = won
            resampled[(b, a)] = games - won
        for k, v in to_elo(fit_strengths(names, resampled), anchor).items():
            samples[k].append(v)
    return {k: (sum((x - sum(v) / len(v)) ** 2 for x in v) / (len(v) - 1)) ** 0.5 for k, v in samples.items()}


def ratings(names, wins, anchor=None, n=BOOTSTRAPS):
    elo = to_elo(fit_strengths(names, wins), anchor)
    se = bootstrap(names, wins, anchor, n)
    return {k: (elo[k], se[k]) for k in names}
