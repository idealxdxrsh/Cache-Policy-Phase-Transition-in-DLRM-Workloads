#!/usr/bin/env python3
"""
Time 26 nn.EmbeddingBag tables against a small MLP in one forward pass (P4).

Model: 26 x EmbeddingBag(rows, dim, mode='sum') -> concat (26*dim) ->
MLP Linear(26*dim, 512) - ReLU - Linear(512, 256) - ReLU - Linear(256, 1).
Inference only (torch.no_grad), fp32, POOLING indices per table per sample.

Per iteration, CUDA events are recorded before the embeddings, between the
embeddings and the MLP, and after the MLP, so the embedding and MLP times come
from the same forward pass. Event times are GPU stream time between the
events: if the CPU cannot launch kernels fast enough, the gaps are included.
CPU wall time per iteration is recorded as well, to see launch-bound runs.
On --device cpu (tests only) time.perf_counter is used instead of events.

Index patterns (all ids in [0, rows)):
  uniform      torch.randint
  zipf<a>      rank r ~ p(r) proportional to r^-a on 1..rows (continuous inverse
               CDF, rounded down), id = ((r-1) * 1000003 + 7919 * table) % rows
  criteo       consecutive ids from the P3 per-table dumps (table_XX.u32),
               id % rows; batch k uses trace positions [k*B*L, (k+1)*B*L)

Usage:
  python3 profile_embedding.py --device cuda --out results/P4/h100 \
      --criteo_dir /scratch/rahulkmr/Adarsh/data/p3/traces_10000000
"""
import argparse
import csv
import json
import math
import os
import platform
import socket
import subprocess
import time

import numpy as np
import torch
from torch import nn

PATTERNS = ['uniform', 'zipf0.6', 'zipf0.85', 'zipf1.1', 'criteo']
ZIPF_MULT = 1000003      # prime, coprime with 2 and 5, so the rank->id map is a bijection
ZIPF_TABLE_SHIFT = 7919
FIELDS = ['status', 'pattern', 'rows', 'dim', 'batch', 'tables', 'pooling', 'iters', 'timer',
          'emb_ms_p10', 'emb_ms_median', 'emb_ms_p90',
          'mlp_ms_p10', 'mlp_ms_median', 'mlp_ms_p90',
          'total_ms_median', 'emb_share_median', 'cpu_wall_ms_per_iter',
          'emb_lookup_bytes', 'emb_lookup_GBps_median', 'criteo_wrapped', 'note']


class Model(nn.Module):
    def __init__(self, tables, rows, dim, device):
        super().__init__()
        self.embs = nn.ModuleList(nn.EmbeddingBag(rows, dim, mode='sum', device=device)
                                  for _ in range(tables))
        self.mlp = nn.Sequential(nn.Linear(tables * dim, 512, device=device), nn.ReLU(),
                                 nn.Linear(512, 256, device=device), nn.ReLU(),
                                 nn.Linear(256, 1, device=device))

    def embed(self, idx, offsets):
        return torch.cat([e(idx[t], offsets) for t, e in enumerate(self.embs)], dim=1)


def zipf_ranks(n, rows, alpha, gen):
    """Ranks in 1..rows with p(r) ~ r^-alpha (continuous inverse CDF)."""
    u = torch.rand(n, generator=gen, dtype=torch.float64)
    if abs(alpha - 1.0) < 1e-9:
        r = torch.exp(u * math.log(rows + 1))
    else:
        b = 1.0 - alpha
        r = (u * ((rows + 1) ** b - 1) + 1) ** (1.0 / b)
    return r.floor().clamp_(1, rows).long()


def make_indices(pattern, rows, steps, tables, n_per_step, seed, criteo_dir=None):
    """Returns (int64 tensor [steps, tables, n_per_step] on CPU, wrapped flag)."""
    gen = torch.Generator().manual_seed(seed)
    if pattern == 'uniform':
        return torch.randint(rows, (steps, tables, n_per_step), generator=gen), False
    if pattern.startswith('zipf'):
        alpha = float(pattern[4:])
        out = torch.empty((steps, tables, n_per_step), dtype=torch.long)
        for t in range(tables):
            r = zipf_ranks(steps * n_per_step, rows, alpha, gen)
            out[:, t, :] = (((r - 1) * ZIPF_MULT + ZIPF_TABLE_SHIFT * t) % rows).view(steps, n_per_step)
        return out, False
    if pattern == 'criteo':
        need = steps * n_per_step
        out = torch.empty((steps, tables, n_per_step), dtype=torch.long)
        wrapped = False
        for t in range(tables):
            a = np.fromfile(os.path.join(criteo_dir, f'table_{t:02d}.u32'), dtype=np.uint32,
                            count=need)
            if len(a) == 0:
                raise ValueError(f'criteo table {t}: empty trace')
            if len(a) < need:
                wrapped = True
                a = np.resize(a, need)
            out[:, t, :] = torch.from_numpy((a.astype(np.int64) % rows).reshape(steps, n_per_step))
        return out, wrapped
    raise ValueError(f'unknown pattern {pattern}')


def pct(x, q):
    return float(np.percentile(np.asarray(x), q))


def run_config(model, idx, offsets, warmup, iters, device):
    """Returns per-iteration lists (emb_ms, mlp_ms) for the timed iterations and CPU wall."""
    emb, mlp = [], []
    cuda = device.type == 'cuda'
    with torch.no_grad():
        if cuda:
            ev = [[torch.cuda.Event(enable_timing=True) for _ in range(3)] for _ in range(warmup + iters)]
        torch.cuda.synchronize() if cuda else None
        t_wall = None
        for k in range(warmup + iters):
            if k == warmup:
                if cuda:
                    torch.cuda.synchronize()
                t_wall = time.perf_counter()
            if cuda:
                ev[k][0].record()
                x = model.embed(idx[k], offsets)
                ev[k][1].record()
                model.mlp(x)
                ev[k][2].record()
            else:
                t0 = time.perf_counter()
                x = model.embed(idx[k], offsets)
                t1 = time.perf_counter()
                model.mlp(x)
                t2 = time.perf_counter()
                if k >= warmup:
                    emb.append((t1 - t0) * 1e3)
                    mlp.append((t2 - t1) * 1e3)
        if cuda:
            torch.cuda.synchronize()
        wall_ms = (time.perf_counter() - t_wall) * 1e3 / iters
        if cuda:
            for k in range(warmup, warmup + iters):
                emb.append(ev[k][0].elapsed_time(ev[k][1]))
                mlp.append(ev[k][1].elapsed_time(ev[k][2]))
    return emb, mlp, wall_ms


def env_info(device):
    info = {'host': socket.gethostname(), 'python': platform.python_version(),
            'torch': torch.__version__, 'torch_cuda': torch.version.cuda,
            'cudnn': torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None,
            'numpy': np.__version__, 'device': str(device)}
    if device.type == 'cuda':
        p = torch.cuda.get_device_properties(device)
        info.update({'gpu_name': p.name, 'gpu_capability': f'{p.major}.{p.minor}',
                     'gpu_total_memory_bytes': p.total_memory,
                     'cuda_visible_devices': os.environ.get('CUDA_VISIBLE_DEVICES')})
        try:
            q = subprocess.run(['nvidia-smi', '--query-gpu=driver_version,name,memory.total',
                                '--format=csv,noheader', '-i', str(torch.cuda.current_device())],
                               capture_output=True, text=True, timeout=60)
            info['nvidia_smi_query'] = q.stdout.strip() or q.stderr.strip()
        except (OSError, subprocess.TimeoutExpired) as e:
            info['nvidia_smi_query'] = f'failed: {e}'
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--out', required=True)
    ap.add_argument('--rows', nargs='+', type=int, default=[1_000_000, 10_000_000])
    ap.add_argument('--dims', nargs='+', type=int, default=[64, 128])
    ap.add_argument('--batches', nargs='+', type=int,
                    default=[64, 128, 256, 512, 1024, 2048, 4096, 8192])
    ap.add_argument('--patterns', nargs='+', default=PATTERNS)
    ap.add_argument('--tables', type=int, default=26)
    ap.add_argument('--pooling', type=int, default=1, help='indices per table per sample')
    ap.add_argument('--warmup', type=int, default=20)
    ap.add_argument('--iters', type=int, default=100)
    ap.add_argument('--criteo_dir', default=None)
    ap.add_argument('--mem_margin_gib', type=float, default=2.0,
                    help='skip a (rows, dim) model if weights + indices + margin exceed free memory')
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()
    if 'criteo' in args.patterns and not args.criteo_dir:
        ap.error('--criteo_dir is required for the criteo pattern')

    device = torch.device(args.device)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, 'env.json'), 'w') as f:
        json.dump({'env': env_info(device), 'args': vars(args)}, f, indent=2)
    path = os.path.join(args.out, 'results.csv')
    f = open(path, 'w', newline='')
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    steps = args.warmup + args.iters
    max_idx_bytes = steps * args.tables * max(args.batches) * args.pooling * 8

    for rows in args.rows:
        for dim in args.dims:
            base = {'rows': rows, 'dim': dim, 'tables': args.tables, 'pooling': args.pooling,
                    'iters': args.iters}
            weight_bytes = args.tables * rows * dim * 4
            if device.type == 'cuda':
                torch.cuda.empty_cache()
                free, _ = torch.cuda.mem_get_info(device)
                need = weight_bytes + max_idx_bytes + int(args.mem_margin_gib * 2**30)
                if need > free:
                    for pattern in args.patterns:
                        for b in args.batches:
                            w.writerow({**base, 'status': 'skipped', 'pattern': pattern, 'batch': b,
                                        'note': f'needs {need} bytes incl. margin, free {free}'})
                    f.flush()
                    print(f'skip rows={rows} dim={dim}: needs {need} B, free {free} B', flush=True)
                    continue
            torch.manual_seed(args.seed)
            model = Model(args.tables, rows, dim, device).eval()
            for pattern in args.patterns:
                for b in args.batches:
                    n = b * args.pooling
                    idx, wrapped = make_indices(pattern, rows, steps, args.tables, n,
                                                args.seed + b, args.criteo_dir)
                    idx = idx.to(device)
                    offsets = torch.arange(0, n, args.pooling, device=device)
                    emb, mlp, wall = run_config(model, idx, offsets, args.warmup, args.iters, device)
                    share = [e / (e + m) for e, m in zip(emb, mlp)]
                    lookup = args.tables * n * dim * 4
                    w.writerow({**base, 'status': 'ok', 'pattern': pattern, 'batch': b,
                                'timer': 'cuda_event' if device.type == 'cuda' else 'perf_counter',
                                'emb_ms_p10': pct(emb, 10), 'emb_ms_median': pct(emb, 50),
                                'emb_ms_p90': pct(emb, 90),
                                'mlp_ms_p10': pct(mlp, 10), 'mlp_ms_median': pct(mlp, 50),
                                'mlp_ms_p90': pct(mlp, 90),
                                'total_ms_median': pct([e + m for e, m in zip(emb, mlp)], 50),
                                'emb_share_median': pct(share, 50),
                                'cpu_wall_ms_per_iter': wall,
                                'emb_lookup_bytes': lookup,
                                'emb_lookup_GBps_median': lookup / (pct(emb, 50) * 1e-3) / 1e9,
                                'criteo_wrapped': wrapped if pattern == 'criteo' else '',
                                'note': ''})
                    f.flush()
                    print(f'rows={rows} dim={dim} {pattern:8} B={b:5} emb {pct(emb, 50):.4f} ms '
                          f'mlp {pct(mlp, 50):.4f} ms', flush=True)
                    del idx
            del model
    f.close()
    print(f'Saved: {path}')


if __name__ == '__main__':
    main()
