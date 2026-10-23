# Characterising the Cache-Policy Phase Transition in DLRM Workloads
### A Hardware-Grounded LFU Controller with Persistent Saturating Counters

**Author:** Adarsh · ID: 2023B1A31167G  
**Institution:** Dept. of Electrical & Electronics Engineering, BITS Pilani Goa Campus  
**Infrastructure:** Sharanga HPC Cluster · NVIDIA H100 80GB HBM3  
**Paper:** [IEEE-format manuscript (Google Drive)](https://drive.google.com/file/d/1aVhKuQW_nInPTzpIDsZzRYGjmGVRbpB3/view?usp=sharing)  
**Synthesis Report:** [Full RTL synthesis report (Google Drive)](https://drive.google.com/file/d/1umN1cXv4_pNinlDdDtOwHcsdoMCzG_UN/view?usp=sharing)

---

## Overview

Deep Learning Recommendation Models (DLRMs) are the dominant inference workload in hyperscale datacenters. This project identifies and empirically characterises a **cache-policy phase transition** in DLRM workloads: LFU replacement is suboptimal in a cold-start regime at small cache capacities, but becomes strictly superior to LRU once the cache is large enough for frequency history to converge on the Zipfian embedding access distribution.

The project spans the full hardware stack — from real GPU profiling to architectural simulation to RTL synthesis and verification.

```
H100 Profiling → Criteo Trace Analysis → gem5 Simulation → RTL Design → Yosys Synthesis (generic gates) → GTKWave Verification
```

### Key Results

| Metric | Value |
|--------|-------|
| EmbeddingBag kernel share of GPU kernel time (H100, job 149046) | **71.8%** (204 µs of 284 µs) |
| gem5 L2 hit rate at 2 MB, LRU → LFU | **54.31% → 55.90%** (+1.59 pp) |
| gem5 L2 misses at 2 MB | **304,590 → 293,995** (−3.48%) |
| Projected end-to-end speedup (Amdahl, f = 0.718, S = 1.036) | **+2.6%** |
| RTL storage, 16 lines, 20-bit tag / 128-bit vector (Yosys, generic gates) | 2,705 flip-flops, 8,626 combinational gates |
| RTL area, power, timing | **not yet measured** (needs a technology library and STA) |

---

## Repository Structure

```
.
├── rtl/
│   ├── v1_verified/                    # design the testbench + GTKWave waveform were run on
│   │   ├── LFU.v                       #   16 lines, 32-bit address, 512-bit data
│   │   ├── tb_lfu_cache.sv
│   │   └── lfu_cache_waves.vcd
│   ├── v1_synthesized/
│   │   └── lfu_cache_controller.v      # 16 lines, 20-bit tag, 128-bit vector (area/power figures)
│   └── v2/                             # 256 lines, 6-bit counters, 2-stage victim select
│       ├── lfu_cache_controller.v
│       ├── tb_lfu_cache.sv             #   self-checking testbench
│       ├── synth.ys                    #   generic Yosys flow
│       └── run_rtl.sh
│
├── gem5/
│   ├── run_dlrm_baseline.py            # LRU, 2 MB L2
│   ├── run_dlrm_cache.py               # LFU, 2 MB L2
│   ├── run_dlrm_baseline_256k.py       # LRU, 256 kB L2
│   ├── run_dlrm_cache_256k.py          # LFU, 256 kB L2
│   └── results/
│       ├── lru_2mb/stats.txt
│       └── lfu_2mb/stats.txt           # (256 kB / 512 kB stats: see results/README.md)
│
├── trace_sim/
│   ├── run_trace_sim.py                # trace-driven LRU / LFU / LFU-reset / TinyLFU simulator
│   ├── plot_trace_results.py           # figure generator
│   ├── submit_trace_sim.sh             # Sharanga SLURM job
│   └── results/                        # trace_sim_results.json goes here
│
├── synthesis/                          # Yosys flow, logs and reruns
├── profiling/
│   └── gpu_profile_149046_out.txt      # raw H100 profiler output (job 149046)
│
├── criteo/                             # dataset, not tracked
├── paper/
│   └── ieee_final.pdf
└── README.md
```

---

## The Core Finding — Cache-Policy Phase Transition

Running 6 controlled gem5 simulations across 3 L2 cache sizes reveals a phase transition:

```
Cache Size │ LRU Hit Rate │ LFU Hit Rate │ Δ DRAM       │ Regime
───────────┼──────────────┼──────────────┼──────────────┼─────────────────
256 kB     │    6.88%     │    0.61%     │ +6.73%       │ Cold-start (LRU wins)
512 kB     │   14.88%     │    5.23%     │ +11.35%      │ Cold-start (LRU wins)
2 MB       │   54.31%     │   55.90%     │ −3.48% ✓     │ Power-law (LFU wins)
```

**Why LFU loses at small sizes:** gem5's LFURP resets frequency counters on eviction. At >90% miss rate, nearly every access triggers an eviction and counter reset — preventing frequency history from accumulating.

**The hardware fix:** Persistent saturating counters in the RTL — `freq_cnt[i]` resets only when line `i` is physically evicted, never on a cache miss. This allows long-term frequency history to accumulate correctly.

> **Status note:** in `rtl/v1_verified/LFU.v` and `rtl/v1_synthesized/lfu_cache_controller.v` a newly installed line starts at count 1, so per-address history across eviction is not implemented in the current RTL. The `trace_sim` LFU-persistent policy models that idealised history. Resolving this is open work.

---

## RTL Design — `lfu_cache_controller.v`

### Parameters

```verilog
parameter CACHE_DEPTH  = 16;    // Number of cache lines
parameter ADDR_WIDTH   = 20;    // Embedding address bits
parameter VECTOR_WIDTH = 128;   // Embedding vector width (bits)
parameter COUNTER_WIDTH = 8;    // Saturating frequency counter (0–255)
```

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  lfu_cache_controller                        │
│                                                             │
│  tag_store[16][20]     ← 20-bit tag per line               │
│  data_store[16][128]   ← 128-bit embedding vector          │
│  freq_cnt[16][8]       ← 8-bit PERSISTENT saturating ctr   │
│  valid_bits[16]        ← valid flag                        │
│                                                             │
│  Hit detection:  16-way 20-bit XNOR comparator tree        │
│  Victim select:  16-way 8-bit magnitude comparator tree     │
│  FSM:            IDLE → LOOKUP → EVICT → FILL              │
└─────────────────────────────────────────────────────────────┘
```

### FSM State Transitions

```
         req_valid=1
IDLE ─────────────────► LOOKUP
 ▲                         │
 │         hit=1           │ miss=1
 └─────────────────────────┤
                           ▼
                         EVICT
                           │
                           ▼
                          FILL ──── fill_valid=1 ────► IDLE
```

### Key Design Decision — Persistent Counters

> **Status note:** in `rtl/v1_verified/LFU.v` and `rtl/v1_synthesized/lfu_cache_controller.v` a newly installed line starts at count 1, so per-address history across eviction is not implemented in the current RTL. The `trace_sim` LFU-persistent policy models that idealised history. Resolving this is open work.

```verilog
// On eviction — invalidate line but PRESERVE frequency counter
valid_bits[victim] <= 0;
tag_store[victim]  <= 0;
data_store[victim] <= 0;
// freq_cnt[victim] intentionally NOT reset

// On fill — counter continues accumulating from previous history
freq_cnt[lfu_idx] <= freq_cnt[lfu_idx] + 1;  // NOT reset to 1
```

This directly addresses the counter-reset-on-eviction deficiency in gem5 LFURP.

---

## Running the RTL Simulation

### Prerequisites

```bash
# Icarus Verilog
sudo apt install iverilog gtkwave    # Ubuntu/Debian
# or
conda install -c conda-forge iverilog

# Verify
iverilog -V
```

### Compile and Simulate

```bash
# Original design (the one behind the GTKWave screenshot)
cd rtl/v1_verified/
iverilog -g2012 -o lfu_sim LFU.v tb_lfu_cache.sv
vvp lfu_sim                       # writes lfu_cache_waves.vcd
gtkwave lfu_cache_waves.vcd

# v2: 256 lines, pipelined victim selection, self-checking testbench
cd ../v2/
bash run_rtl.sh                   # prints ALL TESTS PASSED, then a generic Yosys cell count
```

### What to look for in GTKWave

`rtl/v1_verified/lfu_cache_waves.vcd` (see `rtl/v1_verified/NOTES.md`):

1. **freq_count[13]** reaches 23, **freq_count[15]** reaches 13, **freq_count[14]** reaches 7; every other line stays at 1.
2. These are about double the number of hits: `LFU.v` registers both `next_state` and `current_state`, so each state
   lasts two cycles and a hit increments the counter twice. This is a bug to fix in the RTL.
3. On a miss the FSM goes TAG_CHECK → EVICT_LFU → FETCH_MEM → ALLOCATE.

---

## Running gem5 Simulations

### Prerequisites

```bash
# Clone and build gem5 (on Sharanga compute partition)
git clone https://github.com/gem5/gem5.git
cd gem5
scons build/X86/gem5.opt -j8
```

### Run LRU vs LFU Comparison

```bash
cd gem5/

# LRU baseline — 2MB L2
./build/X86/gem5.opt configs/deprecated/example/se.py \
    --cmd ../dlrm/dlrm_benchmark \
    --l2cache --l2_size=2MB \
    --l2-hwp-type=TaggedPrefetcher \
    --cpu-type=X86TimingSimpleCPU \
    --mem-type=DDR4_2400_8x8 \
    --mem-size=8GB \
    > results/lru_2mb/stats.txt

# LFU proposed — 2MB L2
# Edit configs to use LFURP() replacement policy
# (see run_dlrm_cache.py for full configuration)
```

### Extract Key Metrics

```bash
grep "system.l2cache.overallHits::total" m5out/stats.txt
grep "system.l2cache.overallMisses::total" m5out/stats.txt
grep "system.mem_ctrl.dram.numReads::total" m5out/stats.txt
grep "system.cpu.ipc" m5out/stats.txt
```

---

## Running the Trace-Driven Simulation

### Dataset

The Criteo Terabyte dataset is required. It is not tracked in this repository.

```bash
# Download via Kaggle CLI
pip install kaggle
kaggle competitions download -c criteo-display-ad-challenge
unzip criteo-display-ad-challenge.zip

# Or if already on Sharanga:
ls /scratch/$USER/dlrm/criteo/raw/dac/train.txt
```

### Run Simulation

```bash
cd trace_sim/
mkdir -p results figs logs

# Quick test (100k rows, a few capacities)
python3 run_trace_sim.py \
    --criteo_path /path/to/criteo/train.txt \
    --n_rows 100000 --capacities 100 1000 10000 \
    --workers 4 --output results/

# Full run on Sharanga (CRITEO_PATH can be overridden from the environment)
sbatch submit_trace_sim.sh

# Plot results
python3 plot_trace_results.py \
    --results results/trace_sim_results.json \
    --output figs/
```

### Policies Compared

| Policy | Description |
|--------|-------------|
| LRU | Standard Least Recently Used |
| LFU-persistent | LFU with per-address history kept after eviction (idealised model) |
| LFU-gem5-reset | LFU that forgets an address's count on eviction (hypothesised gem5 LFURP behaviour) |
| TinyLFU | Window-LRU admission + LFU main cache, exact counters (idealised) |

---

## H100 Profiling

```bash
cd profiling/
sbatch run_gpu_profiler.sh        # script still to be copied from Sharanga
```

Raw output: `gpu_profile_149046_out.txt`. See `profiling/README.md` for what the numbers do and do not show.

---

## Synthesis

`synthesis/` holds the Yosys flow (`synth.tcl`: `synth; abc -g cmos2; stat`), your log, and reruns for both RTL
configurations. This flow uses generic gates and no technology library.

| Run | Flip-flops | Combinational gates | Total cells |
|-----|-----------:|--------------------:|------------:|
| `LFU.v` as simulated (32-bit address, 512-bit data) | 9,449 | 24,704 | 34,153 |
| paper configuration (20-bit tag, 128-bit vector) | 2,705 | 8,626 | 11,331 |

Longest topological path: about 245 gate levels. **No area (µm²), power or Fmax has been measured.** Doing that
needs a liberty file (NanGate45, ASAP7 or SKY130 are freely available) and OpenSTA.

---

## Amdahl Speedup Calculation

```
f  = 0.7184   (EmbeddingBag kernel share of GPU kernel time, job 149046: 204.065 us / 284.063 us)
S  = 1.036    (gem5 2 MB L2 misses, LRU / LFU = 304,590 / 293,995)

Speedup = 1 / [(1 − f) + f/S] = 1.0256  →  +2.6% end-to-end
```

This is a projection that assumes the fewer L2 misses translate fully into shorter embedding time. In gem5 itself
the IPC change at 2 MB is only +0.08% (0.2357 → 0.2359).

---

## Dependencies

```
Python       ≥ 3.8
matplotlib   ≥ 3.5
numpy        ≥ 1.21
iverilog     ≥ 11.0
gtkwave      ≥ 3.3
gem5         (cloned from gem5/gem5 — built on Sharanga)
PyTorch      ≥ 2.0   (for H100 profiling)
```

---

## Limitations & Future Work

- **Simulation gap:** gem5 SE-mode uses a CPU and DDR4, not a GPU and HBM. The trace-driven simulation closes part of this gap for the policy comparison.
- **Profiling:** the H100 run is launch-bound (284 µs of kernels in a 4.1 ms run). A memory-bound claim needs a larger batch and hardware counters.
- **RTL:** `LFU.v` has a two-cycle-per-state FSM bug (counters double-count). `rtl/v2` fixes the structure and is simulated, not synthesized.
- **Counters:** both v1 files start a newly installed line at count 1; they do not keep per-address history across eviction.
- **Synthesis:** generic-gate counts only; no technology library, area, power or timing yet.
- **Baselines:** the TinyLFU model uses exact counters (an upper bound); a real sketch-based TinyLFU is not implemented.

---

## Citation

```bibtex
@techreport{adarsh2026dlrm,
  title     = {Characterising the Cache-Policy Phase Transition in DLRM Workloads:
               A Hardware-Grounded LFU Controller with Persistent Saturating Counters},
  author    = {Adarsh},
  institution = {BITS Pilani Goa Campus, Dept. of EEE},
  year      = {2026},
  note      = {Manuscript in preparation — arXiv cs.AR submission.
               Sharanga HPC Research.}
}
```

---

## License

© 2026 Adarsh (ID: 2023B1A31167G). All rights reserved.  
Department of Electrical & Electronics Engineering, BITS Pilani Goa Campus.  
Not for redistribution without explicit written permission.

---

*Sharanga HPC · NVIDIA H100 80GB HBM3 · BITS Pilani Goa · 2026*
