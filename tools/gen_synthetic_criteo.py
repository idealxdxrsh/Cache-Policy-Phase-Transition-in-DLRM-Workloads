#!/usr/bin/env python3
"""
Write a SYNTHETIC file in Criteo Kaggle train.txt layout, for testing only.

Layout per line (tab-separated, 40 fields):
  col 0      label 0/1
  cols 1-13  integer dense features (some empty)
  cols 14-39 26 categorical features as 8-digit lowercase hex (some empty)

Each categorical column draws ids from its own Zipf-like distribution
(p(rank) ~ rank^-alpha over a finite vocabulary). Nothing produced here is
real Criteo data; hit rates from it must never be reported as results.

Usage:
    python3 tools/gen_synthetic_criteo.py --rows 20000 --out /tmp/synth.txt
"""
import argparse

import numpy as np

N_DENSE, N_CAT = 13, 26


def column_params(n_cat=N_CAT):
    """Per-table (alpha, vocab): alphas 0.6..1.2, vocab 1e2..1e5."""
    alphas = np.linspace(0.6, 1.2, n_cat)
    vocabs = np.round(np.logspace(2, 5, n_cat)).astype(int)
    return list(zip(alphas.tolist(), vocabs.tolist()))


def zipf_sampler(rng, alpha, vocab):
    p = np.arange(1, vocab + 1, dtype=np.float64) ** -alpha
    cdf = np.cumsum(p / p.sum())
    ids = rng.choice(1 << 32, size=vocab, replace=False)   # distinct 32-bit ids
    return lambda n: ids[np.minimum(np.searchsorted(cdf, rng.random(n)), vocab - 1)]


def generate(path, rows, seed=0, missing=0.05):
    rng = np.random.default_rng(seed)
    params = column_params()
    samplers = [zipf_sampler(rng, a, v) for a, v in params]
    with open(path, 'w') as f:
        chunk = 10_000
        for start in range(0, rows, chunk):
            n = min(chunk, rows - start)
            labels = rng.integers(0, 2, n)
            dense = rng.integers(0, 1000, (n, N_DENSE))
            dense_miss = rng.random((n, N_DENSE)) < missing
            cats = np.stack([s(n) for s in samplers], axis=1)
            cat_miss = rng.random((n, N_CAT)) < missing
            for i in range(n):
                d = ['' if dense_miss[i, j] else str(dense[i, j]) for j in range(N_DENSE)]
                c = ['' if cat_miss[i, j] else f'{cats[i, j]:08x}' for j in range(N_CAT)]
                f.write('\t'.join([str(labels[i])] + d + c) + '\n')
    return params


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--rows', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    generate(args.out, args.rows, args.seed)
    print(f"wrote {args.rows} synthetic rows to {args.out}")


if __name__ == '__main__':
    main()
