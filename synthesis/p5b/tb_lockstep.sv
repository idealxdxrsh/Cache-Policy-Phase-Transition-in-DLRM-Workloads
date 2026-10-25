// Lockstep check (P5b): the baseline RTL (git tag rtl-v2-baseline, module renamed to
// lfu_cache_controller_base by run_lockstep.sh) and the current RTL get the same random
// stimulus; every output is compared at every rising clock edge. Any difference, in
// value or in cycle, is a mismatch. Also compared: the victim slot index in every EVICT
// cycle (internal; the ports alone cannot see the tie-break order, because any fixed
// slot-priority order gives the same port behaviour from an empty cache).
// P5d: also compared: hit_idx in every LOOKUP cycle with a hit; and checked every cycle:
// at most one entry matches (no duplicate valid tags), in both designs.
`timescale 1ns / 1ps
module tb_lockstep #(parameter COUNTER_MODE = 0, parameter CACHE_DEPTH = 256,
                     parameter CYCLES = 200000, parameter SEED = 1);
localparam AW = 20, VW = 128;
reg clk = 0, rst_n = 0;
always #0.5 clk = ~clk;
reg req_valid = 0, fill_valid = 0;
reg [AW-1:0] req_addr = 0;
reg [VW-1:0] fill_data = 0;
wire rv_a, hf_a, fr_a, rv_b, hf_b, fr_b;
wire [VW-1:0] rd_a, rd_b;
wire [AW-1:0] fa_a, fa_b;
lfu_cache_controller_base #(.CACHE_DEPTH(CACHE_DEPTH), .COUNTER_MODE(COUNTER_MODE)) base (
    .clk(clk), .rst_n(rst_n), .req_valid(req_valid), .req_addr(req_addr),
    .resp_valid(rv_a), .resp_data(rd_a), .hit_flag(hf_a), .fill_req(fr_a), .fill_addr(fa_a),
    .fill_valid(fill_valid), .fill_data(fill_data));
lfu_cache_controller #(.CACHE_DEPTH(CACHE_DEPTH), .COUNTER_MODE(COUNTER_MODE)) dut (
    .clk(clk), .rst_n(rst_n), .req_valid(req_valid), .req_addr(req_addr),
    .resp_valid(rv_b), .resp_data(rd_b), .hit_flag(hf_b), .fill_req(fr_b), .fill_addr(fa_b),
    .fill_valid(fill_valid), .fill_data(fill_data));
integer cyc = 0, mism = 0, vmism = 0, hmism = 0, multi = 0, n_lkhit = 0, n_evict = 0, n_req = 0, n_hit = 0, n_fill = 0, seed = SEED;
integer pool;
function integer rnd(input integer unused);   // non-negative, advances seed
    rnd = $random(seed) & 32'h7fffffff;
endfunction
always @(posedge clk) if (rst_n) begin
    cyc = cyc + 1;
    if ({rv_a, hf_a, fr_a, rd_a, fa_a} !== {rv_b, hf_b, fr_b, rd_b, fa_b}) begin
        mism = mism + 1;
        if (mism <= 5) $display("MISMATCH cycle %0d: base rv=%b hf=%b fr=%b fa=%h | new rv=%b hf=%b fr=%b fa=%h",
                                cyc, rv_a, hf_a, fr_a, fa_a, rv_b, hf_b, fr_b, fa_b);
    end
    if (base.state == 2'b10) begin
        n_evict = n_evict + 1;
        if (base.victim_comb !== dut.victim_comb || dut.state !== 2'b10) begin
            vmism = vmism + 1;
            if (vmism <= 5) $display("VICTIM MISMATCH cycle %0d: base %0d new %0d", cyc, base.victim_comb, dut.victim_comb);
        end
    end
    if (base.state == 2'b01 && base.hit_detected) begin
        n_lkhit = n_lkhit + 1;
        if (base.hit_idx !== dut.hit_idx) begin
            hmism = hmism + 1;
            if (hmism <= 5) $display("HIT_IDX MISMATCH cycle %0d: base %0d new %0d", cyc, base.hit_idx, dut.hit_idx);
        end
    end
    // more than one bit set  <=>  (m & (m - 1)) != 0
    if (|(base.match & (base.match - 1'b1)) || |(dut.match & (dut.match - 1'b1))) begin
        multi = multi + 1;
        if (multi <= 5) $display("MULTIPLE MATCHES cycle %0d: base %0d new %0d", cyc, $countones(base.match), $countones(dut.match));
    end
    if (rv_a) n_req = n_req + 1;
    if (hf_a) n_hit = n_hit + 1;
    if (fr_a) n_fill = n_fill + 1;
end
// Stimulus on the falling edge: random requests from a pool of 2*CACHE_DEPTH addresses
// (half hot), random request gaps, random fill delay 0-3 cycles; req_valid is also driven
// at random while the controller is busy (it is ignored outside IDLE).
integer d;
initial begin
    repeat (3) @(negedge clk);
    rst_n = 1;
    while (cyc < CYCLES) begin
        @(negedge clk);
        pool = (rnd(0) % 4 == 0) ? 2 * CACHE_DEPTH : CACHE_DEPTH / 4 + 1;
        req_valid = (rnd(0) % 3) != 0;
        req_addr = 20'h40000 + (rnd(0) % pool);
        if (fr_a) begin
            d = rnd(0) % 4;
            req_valid = 0;
            repeat (d) @(negedge clk);
            fill_valid = 1; fill_data = {rnd(0), rnd(0), rnd(0), rnd(0)};
            @(negedge clk);
            fill_valid = 0;
        end
    end
    $display("lockstep depth=%0d mode=%0d cycles=%0d responses=%0d hits=%0d fills=%0d evicts=%0d port_mismatches=%0d victim_mismatches=%0d lookup_hits=%0d hit_idx_mismatches=%0d multi_match_cycles=%0d",
             CACHE_DEPTH, COUNTER_MODE, cyc, n_req, n_hit, n_fill, n_evict, mism, vmism, n_lkhit, hmism, multi);
    if (mism == 0 && vmism == 0 && hmism == 0 && multi == 0 && n_hit > 0 && n_evict > 0) $display("LOCKSTEP PASSED");
    else                                       $display("LOCKSTEP FAILED");
    $finish;
end
endmodule
