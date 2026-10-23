# 1. Read the Verilog design
read_verilog lfu_cache.v

# 2. Run the generic synthesis macro for the top module
synth -top lfu_cache_controller

# 3. Map to generic CMOS gates for an area estimate
abc -g cmos2

# 4. Clean up unused wires
clean

# 5. Print the hardware statistics
stat