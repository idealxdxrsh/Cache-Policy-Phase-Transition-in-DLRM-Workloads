import m5
from m5.objects import *

# --- 1. DEFINE OUR CUSTOM CACHES ---
class L1Cache(Cache):
    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20

class L1ICache(L1Cache):
    size = '16kB'

class L1DCache(L1Cache):
    size = '64kB'

class L2Cache(Cache):
    size = '2MB'  # Large enough to hold "Hot" DLRM Embeddings
    assoc = 8
    tag_latency = 20
    data_latency = 20
    response_latency = 20
    mshrs = 20
    tgts_per_mshr = 12
    # *** THE SECRET WEAPON: FREQUENCY CACHE POLICY ***
    replacement_policy = LFURP() 

# --- 2. BUILD THE MOTHERBOARD ---
system = System()
system.clk_domain = SrcClockDomain(clock = '2GHz', voltage_domain = VoltageDomain())
system.mem_mode = 'timing'
system.mem_ranges = [AddrRange('8GB')]

# --- 3. ADD CPU & CACHES ---
system.cpu = X86TimingSimpleCPU()
system.cpu.icache = L1ICache()
system.cpu.dcache = L1DCache()

# Connect CPU to L1 Caches
system.cpu.icache.cpu_side = system.cpu.icache_port
system.cpu.dcache.cpu_side = system.cpu.dcache_port

# Create an L2 Bus to connect L1s to L2
system.l2bus = L2XBar()
system.cpu.icache.mem_side = system.l2bus.cpu_side_ports
system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports

# Connect L2 Cache to L2 Bus and Main Memory Bus
system.l2cache = L2Cache()
system.l2cache.cpu_side = system.l2bus.mem_side_ports
system.membus = SystemXBar()
system.l2cache.mem_side = system.membus.cpu_side_ports

system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports

system.system_port = system.membus.cpu_side_ports

# --- 4. ADD HBM/MAIN MEMORY ---
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR4_2400_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

# --- 5. RUN A TEST WORKLOAD ---
process = Process()
process.executable = 'dlrm_benchmark'
process.cmd = ['dlrm_benchmark']

# Tell the system to create an environment compatible with our binary
system.workload = SEWorkload.init_compatible(process.executable)

system.cpu.workload = process
system.cpu.createThreads()

# Tell the system to create an environment compatible with our binary
system.workload = SEWorkload.init_compatible(process.executable)

system.cpu.workload = process
#system.cpu.createThreads()

# --- 6. START SIMULATION ---
root = Root(full_system=False, system=system)
m5.instantiate()

print("Starting DLRM Architecture Simulation...")
exit_event = m5.simulate()
print(f"Simulation finished at tick {m5.curTick()} because {exit_event.getCause()}")
