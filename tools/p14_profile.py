#!/usr/bin/env python3
"""P14 (GPU): nn.EmbeddingBag on the real Criteo stream, for ncu.

Stream: stream.npz from tools/p14_prep_stream.py (first 2M rows, 26 tables, dense ids, -1 = no access).
One batch = B consecutive Criteo rows. Each (row, table) is one bag of 0 or 1 lookups (mode='sum').
  per_table: 26 EmbeddingBag(n_t, dim) tables; per batch 26 calls (tables 0..25), one kernel each.
  concat:    one EmbeddingBag(sum n_t, dim); table t occupies rows [base_t, base_t + n_t); per batch
             one call with 26*B bags in row-major (row, table) order, the P3b access order.
All index and offset tensors are built on the GPU before the loop; inside it, inputs are views
(no copies or extra kernels). Batches 0 .. start_row/B - 1 are warmup (not profiled); then
cudaProfilerStart, batches start_row/B .. +batches-1, cudaProfilerStop (ncu --profile-from-start off).
Writes <out>/run.json: rows profiled, lookups per table and in total, L2 size from torch.
"""
import argparse
import json
import os
import time

import numpy as np
import torch
from torch import nn


def offsets_local(present, B):
    """present: bool [n_bags]; bags grouped in batches of B bags. Returns (c, off):
    c[q] = lookups before bag q (len n_bags+1); off[q] = c[q] - c[first bag of q's batch]."""
    c = np.zeros(len(present) + 1, dtype=np.int64)
    np.cumsum(present, out=c[1:])
    first = (np.arange(len(present)) // B) * B
    return c, c[:-1] - c[first]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stream', required=True)
    ap.add_argument('--mode', choices=['per_table', 'concat'], required=True)
    ap.add_argument('--batch', type=int, required=True)
    ap.add_argument('--start_row', type=int, default=1 << 20)
    ap.add_argument('--batches', type=int, default=20)
    ap.add_argument('--dim', type=int, default=128)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    B, S, K = a.batch, a.start_row, a.batches
    assert S % B == 0, 'start_row must be a multiple of batch'
    z = np.load(a.stream)
    dense, card = z['dense'], z['card']
    n_rows, T = dense.shape
    end = S + K * B
    assert end <= n_rows
    dense = dense[:end]
    dev = torch.device('cuda')
    torch.manual_seed(a.seed)
    t0 = time.time()
    present = dense >= 0
    if a.mode == 'per_table':
        embs, idx, off = [], [], []
        for t in range(T):
            embs.append(nn.EmbeddingBag(int(card[t]), a.dim, mode='sum', device=dev).requires_grad_(False))
            c, o = offsets_local(present[:, t], B)
            idx.append(torch.from_numpy(dense[present[:, t], t].astype(np.int64)).to(dev))
            off.append((c, torch.from_numpy(o).to(dev)))

        def step(k):
            r0 = k * B
            for t in range(T):
                c, o = off[t]
                embs[t](idx[t][int(c[r0]):int(c[r0 + B])], o[r0:r0 + B])
    else:
        base = np.concatenate([[0], np.cumsum(card)[:-1]]).astype(np.int64)
        emb = nn.EmbeddingBag(int(card.sum()), a.dim, mode='sum', device=dev).requires_grad_(False)
        flat = (dense.astype(np.int64) + base[None, :]).reshape(-1)  # row-major (row, table)
        pf = present.reshape(-1)
        c, o = offsets_local(pf, T * B)
        idx_g = torch.from_numpy(flat[pf]).to(dev)
        off_g = torch.from_numpy(o).to(dev)

        def step(k):
            q0 = k * B * T
            emb(idx_g[int(c[q0]):int(c[q0 + T * B])], off_g[q0:q0 + T * B])
    torch.cuda.synchronize()
    t_build = time.time() - t0
    with torch.no_grad():
        t0 = time.time()
        for k in range(S // B):
            step(k)
        torch.cuda.synchronize()
        t_warm = time.time() - t0
        torch.cuda.profiler.start()
        for k in range(S // B, S // B + K):
            step(k)
        torch.cuda.synchronize()
        torch.cuda.profiler.stop()
    prof = present[S:end]
    props = torch.cuda.get_device_properties(0)
    res = {'mode': a.mode, 'batch': B, 'dim': a.dim, 'dtype': 'float32', 'seed': a.seed,
           'warmup_rows': [0, S], 'warmup_batches': S // B,
           'profiled_rows': [S, end], 'profiled_batches': K,
           'profiled_lookups_total': int(prof.sum()),
           'profiled_lookups_per_table': [int(x) for x in prof.sum(axis=0)],
           'profiled_empty_table_batches': int(sum((prof[k * B:(k + 1) * B, t].sum() == 0)
                                                   for k in range(K) for t in range(T))),
           'expected_embedding_calls': K * (T if a.mode == 'per_table' else 1),
           'table_rows': [int(x) for x in card], 'total_vectors': int(card.sum()),
           'gpu': props.name, 'l2_cache_size_bytes': getattr(props, 'L2_cache_size', None),
           'torch': torch.__version__, 'build_s': round(t_build, 3), 'warmup_s': round(t_warm, 3)}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'run.json'), 'w') as f:
        json.dump(res, f, indent=1)
    print('P14_RUN', json.dumps({k: res[k] for k in ('mode', 'batch', 'profiled_rows', 'profiled_lookups_total',
                                                     'l2_cache_size_bytes', 'warmup_s')}))


if __name__ == '__main__':
    main()
