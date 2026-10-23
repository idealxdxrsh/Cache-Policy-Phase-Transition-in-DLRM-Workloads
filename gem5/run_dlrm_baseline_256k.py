"""
run_dlrm_baseline_256k.py
─────────────────────────────────────────────────────────────
gem5 SE-mode DLRM baseline — LRU replacement, 256 KB L2
Change from 2 MB run: L2Cache.size = '256kB'

Rationale: 256 KB is closer to a realistic on-die scratchpad
target for the LFU hardware controller. At this capacity the
power-law embedding distribution creates a much sharper
hit-rate gap between LRU and LFU, amplifying the IPC delta.

Submit on Sharanga:
    sbatch --gres=gpu:0 --cpus-per-task=4 --mem=16G \
           --job-name=dlrm_lru_256k \
           --output=lru_256k_%j.out \
           --wrap="python run_dlrm_baseline_256k.py"
"""

import m5
from m5.objects import *

# ── 1. CACHE DEFINITIONS ─────────────────────────────────────

class L1Cache(Cache):
    assoc            = 2
    tag_latency      = 2
    data_latency     = 2
    response_latency = 2
    mshrs            = 4
    tgts_per_mshr    = 20

class L1ICache(L1Cache):
    size = '16kB'

class L1DCache(L1Cache):
    size = '64kB'

class L2Cache(Cache):
    # *** KEY CHANGE: 256 kB instead of 2 MB ***
    size             = '256kB'
    assoc            = 8
    tag_latency      = 20
    data_latency     = 20
    response_latency = 20
    mshrs            = 20
    tgts_per_mshr    = 12
    replacement_policy = LRURP()          # BASELINE — LRU

# ── 2. SYSTEM ────────────────────────────────────────────────

system = System()
system.clk_domain  = SrcClockDomain(
    clock          = '2GHz',
    voltage_domain = VoltageDomain()
)
system.mem_mode   = 'timing'
system.mem_ranges = [AddrRange('8GB')]

# ── 3. CPU + CACHE HIERARCHY ─────────────────────────────────

system.cpu    = X86TimingSimpleCPU()
system.cpu.icache = L1ICache()
system.cpu.dcache = L1DCache()

system.cpu.icache.cpu_side = system.cpu.icache_port
system.cpu.dcache.cpu_side = system.cpu.dcache_port

system.l2bus = L2XBar()
system.cpu.icache.mem_side = system.l2bus.cpu_side_ports
system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports

system.l2cache = L2Cache()
system.l2cache.cpu_side = system.l2bus.mem_side_ports

system.membus = SystemXBar()
system.l2cache.mem_side = system.membus.cpu_side_ports

system.cpu.createInterruptController()
system.cpu.interrupts[0].pio          = system.membus.mem_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports

system.system_port = system.membus.cpu_side_ports

# ── 4. MEMORY ────────────────────────────────────────────────

system.mem_ctrl      = MemCtrl()
system.mem_ctrl.dram = DDR4_2400_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

# ── 5. WORKLOAD ──────────────────────────────────────────────

process           = Process()
process.executable = 'dlrm_benchmark'
process.cmd        = ['dlrm_benchmark']

system.workload = SEWorkload.init_compatible(process.executable)
system.cpu.workload = process
system.cpu.createThreads()

# ── 6. RUN ───────────────────────────────────────────────────

root = Root(full_system=False, system=system)
m5.instantiate()

print("=" * 60)
print("  DLRM gem5 Simulation — LRU baseline, 256 kB L2")
print("=" * 60)
exit_event = m5.simulate()
print(f"Finished at tick {m5.curTick()} | cause: {exit_event.getCause()}")
