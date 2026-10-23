# H100 profiling (job 149046)

What the raw output contains:

| Item | Self CUDA time | Note |
|------|---------------:|------|
| EmbeddingBag kernel (26 calls) | 204.065 us | 71.84% of all GPU kernel time |
| all GPU kernels | 284.063 us | "Self CUDA time total" |
| wall-clock (Self CPU total) | 4.140 ms | GPU kernels were active ~7% of the run |
| `2_sparse_memory_lookups` range | 1.617 ms | user-annotated range, shown as 569% |
| `1_dense_compute_mlp` range | 313.855 us | user-annotated range, shown as 110% |

The earlier "83.74%" and "5.15x" came from the two annotated ranges: 1.617 / (1.617 + 0.3139). Those ranges are
longer than the total kernel time (they include launch gaps and idle time), so the ratio is not a measure of memory
stalls. The kernel-level share is 71.8%, and the run is launch-bound (a very small batch), not shown to be
memory-bound.

To support a memory-bound claim: use a production-sized batch and table sizes, and collect hardware counters
(Nsight Compute: dram__throughput, sm__throughput, achieved occupancy).

Still to copy from Sharanga: `profile_baseline_gpu.py`, `run_gpu_profiler.sh`, `h100_trace.json`.
