"""P14 smoke test for GPU performance counters (ncu).

One EmbeddingBag(1,000,000 x 128, fp32, mode='sum') on CUDA, 1,000 bags of one lookup each
(uniform random indices, seed 0). One warmup call runs outside the profiled range; the
profiled range (cudaProfilerStart/Stop, for ncu --profile-from-start off) holds exactly one
call. Prints a checksum so the run can be compared between GPUs.
"""
import argparse

import torch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_000_000)
    ap.add_argument("--dim", type=int, default=128)
    ap.add_argument("--lookups", type=int, default=1_000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    assert torch.cuda.is_available(), "CUDA not available"
    dev = torch.device("cuda")
    torch.manual_seed(a.seed)  # weight init; P14 job 453624 (H100) ran without this line
    g = torch.Generator(device="cpu").manual_seed(a.seed)
    emb = torch.nn.EmbeddingBag(a.rows, a.dim, mode="sum").to(dev)
    idx = torch.randint(0, a.rows, (a.lookups,), generator=g).to(dev)
    off = torch.arange(a.lookups, device=dev)  # bag size 1
    with torch.no_grad():
        emb(idx, off)  # warmup, not profiled
        torch.cuda.synchronize()
        torch.cuda.profiler.start()
        out = emb(idx, off)
        torch.cuda.synchronize()
        torch.cuda.profiler.stop()
    print(f"P14_SMOKE rows={a.rows} dim={a.dim} lookups={a.lookups} seed={a.seed} "
          f"out_shape={tuple(out.shape)} checksum={out.double().sum().item():.6f} "
          f"gpu={torch.cuda.get_device_name(0)} torch={torch.__version__}")


if __name__ == "__main__":
    main()
