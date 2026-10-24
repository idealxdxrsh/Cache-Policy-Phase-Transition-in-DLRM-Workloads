// ============================================================
// Self-checking testbench - LFU Cache Controller v2
// Author: Adarsh (2023B1A31167G), BITS Pilani Goa
// Every check increments `errors`; the final banner reflects
// the real result. Exit text is "ALL TESTS PASSED" only if
// errors == 0.
// ============================================================
`timescale 1ns / 1ps

// COUNTER_MODE and CACHE_DEPTH are set from the command line:
//   iverilog -P tb_lfu_cache.COUNTER_MODE=1 -P tb_lfu_cache.CACHE_DEPTH=64 ...
// Pass +vcd to vvp to dump waveforms.
module tb_lfu_cache #(parameter COUNTER_MODE = 0, parameter CACHE_DEPTH = 256);

localparam ADDR_WIDTH    = 20;
localparam VECTOR_WIDTH  = 128;
localparam COUNTER_WIDTH = 6;

reg clk = 0;
reg rst_n = 0;
always #0.5 clk = ~clk;                       // 1 GHz

reg                      req_valid = 0;
reg  [ADDR_WIDTH-1:0]    req_addr  = 0;
wire                     resp_valid, hit_flag, fill_req;
wire [VECTOR_WIDTH-1:0]  resp_data;
wire [ADDR_WIDTH-1:0]    fill_addr;
reg                      fill_valid = 0;
reg  [VECTOR_WIDTH-1:0]  fill_data  = 0;

lfu_cache_controller #(
    .CACHE_DEPTH(CACHE_DEPTH), .ADDR_WIDTH(ADDR_WIDTH),
    .VECTOR_WIDTH(VECTOR_WIDTH), .COUNTER_WIDTH(COUNTER_WIDTH),
    .COUNTER_MODE(COUNTER_MODE)
) dut (
    .clk(clk), .rst_n(rst_n),
    .req_valid(req_valid), .req_addr(req_addr),
    .resp_valid(resp_valid), .resp_data(resp_data), .hit_flag(hit_flag),
    .fill_req(fill_req), .fill_addr(fill_addr),
    .fill_valid(fill_valid), .fill_data(fill_data)
);

initial begin
    if ($test$plusargs("vcd")) begin
        $dumpfile("lfu_cache_waves.vcd");
        $dumpvars(0, tb_lfu_cache);
    end
end

integer errors = 0;
integer n_acc = 0, n_hit = 0;

function [VECTOR_WIDTH-1:0] payload(input [ADDR_WIDTH-1:0] a);
    payload = {{(VECTOR_WIDTH-ADDR_WIDTH){1'b0}}, a};
endfunction

task check(input cond, input string msg);
    if (!cond) begin
        errors = errors + 1;
        $display("  FAIL: %s", msg);
    end
endtask

task do_reset;
    begin
        rst_n = 0; req_valid = 0; fill_valid = 0;
        repeat (3) @(posedge clk);
        rst_n = 1;
        repeat (2) @(posedge clk);
    end
endtask

// One access. Services the fill handshake on a miss.
task automatic access(input [ADDR_WIDTH-1:0] addr, output reg hit);
    integer t;
    begin
        @(negedge clk);
        req_valid = 1; req_addr = addr;
        @(posedge clk); #0.1;
        req_valid = 0;
        n_acc = n_acc + 1;
        t = 0;
        while (!resp_valid && t < 1000) begin
            if (fill_req) begin
                @(posedge clk); #0.1;
                fill_valid = 1; fill_data = payload(addr);
                @(posedge clk); #0.1;
                fill_valid = 0;
            end else begin
                @(posedge clk); #0.1;
            end
            t = t + 1;
        end
        check(t < 1000, "access timed out");
        hit = hit_flag;
        if (hit) n_hit = n_hit + 1;
        check(resp_data === payload(addr), "response data does not match address");
        @(negedge clk);
    end
endtask

// Counter value of the slot currently holding `addr` (-1 if absent)
function integer slot_count(input [ADDR_WIDTH-1:0] addr);
    integer k;
    begin
        slot_count = -1;
        for (k = 0; k < CACHE_DEPTH; k = k + 1)
            if (dut.valid_bits[k] && dut.tag_store[k] == addr)
                slot_count = dut.freq_cnt[k];
    end
endfunction

integer i, j, hits_seen, missing;
reg h;
real hit_rate;

initial begin
    $display("LFU Cache Controller v2 testbench  (DEPTH=%0d, COUNTER=%0d bits, COUNTER_MODE=%0d)",
             CACHE_DEPTH, COUNTER_WIDTH, COUNTER_MODE);

    // ---- TEST 1: miss then hit, data correct -----------------
    $display("[1] miss then hit");
    do_reset;
    access(20'hAAAA0, h); check(h == 0, "first access must miss");
    access(20'hAAAA0, h); check(h == 1, "second access must hit");

    // ---- TEST 2: full capacity is usable ---------------------
    $display("[2] fill all %0d lines, then re-scan", CACHE_DEPTH);
    do_reset;
    for (i = 0; i < CACHE_DEPTH; i = i + 1) access(20'hC0000 + i, h);
    hits_seen = 0;
    for (i = 0; i < CACHE_DEPTH; i = i + 1) begin
        access(20'hC0000 + i, h);
        hits_seen = hits_seen + h;
    end
    $display("    re-scan hits: %0d / %0d", hits_seen, CACHE_DEPTH);
    check(hits_seen == CACHE_DEPTH, "not all lines retained after filling an empty cache");

    // ---- TEST 3: hot line survives pressure ------------------
    $display("[3] hot line survives 300 unique cold accesses");
    do_reset;
    for (i = 0; i < 20; i = i + 1) access(20'hEEEE0, h);
    for (i = 0; i < 300; i = i + 1) access(20'hB0000 + i, h);
    access(20'hEEEE0, h);
    check(h == 1, "hot line was evicted while colder lines were available");

    // ---- TEST 4: counter saturates at 2^W - 1 ----------------
    $display("[4] counter saturates at %0d", (1 << COUNTER_WIDTH) - 1);
    do_reset;
    for (i = 0; i < 100; i = i + 1) access(20'hFACE0, h);
    check(slot_count(20'hFACE0) == (1 << COUNTER_WIDTH) - 1,
          "counter did not saturate at max value");
    access(20'hFACE0, h);
    check(h == 1, "saturated line must still hit");

    // ---- TEST 5: Zipf-like workload --------------------------
    $display("[5] skewed workload (10 hot addrs ~80%%, 300 cold ~20%%)");
    do_reset;
    n_acc = 0; n_hit = 0;
    for (i = 0; i < 2000; i = i + 1) begin
        if ((i % 5) < 4) access(20'hA0000 + (i % 10), h);
        else             access(20'hB0000 + ((i * 7) % 300), h);
    end
    hit_rate = 100.0 * n_hit / n_acc;
    $display("    accesses=%0d hits=%0d hit-rate=%0.2f%%", n_acc, n_hit, hit_rate);
    check(hit_rate > 70.0, "hit rate below 70% on skewed workload");

    // ---- TEST 6: one access = exactly one counter increment --
    $display("[6] counter equals number of accesses (1 fill + 9 hits = 10)");
    do_reset;
    for (i = 0; i < 10; i = i + 1) access(20'h12345, h);
    check(slot_count(20'h12345) == 10, "counter not incremented exactly once per access");

    // ---- TEST 7: count of a newly installed tag --------------
    // All CACHE_DEPTH lines at count 3; slot 0 (lowest index) is the victim.
    $display("[7] install count after eviction (mode %0d)", COUNTER_MODE);
    do_reset;
    for (i = 0; i < CACHE_DEPTH; i = i + 1) access(20'hD0000 + i, h);
    for (j = 0; j < 2; j = j + 1)
        for (i = 0; i < CACHE_DEPTH; i = i + 1) access(20'hD0000 + i, h);
    access(20'hDEAD0, h);
    check(h == 0, "new address must miss");
    check(slot_count(20'hD0000) == -1, "victim was not the lowest-index min-count line");
    missing = 0;
    for (i = 1; i < CACHE_DEPTH; i = i + 1)
        if (slot_count(20'hD0000 + i) != 3) missing = missing + 1;
    check(missing == 0, "a non-victim line was lost or its count changed");
    if (COUNTER_MODE == 0)
        check(slot_count(20'hDEAD0) == 1, "mode 0: installed tag count must be 1");
    else
        check(slot_count(20'hDEAD0) == 4, "mode 1: installed tag must continue slot count (3+1)");
    // A second new tag: mode 0 evicts the fresh line (count 1),
    // mode 1 evicts slot 1 (count 3 < 4).
    access(20'hBEEF0, h);
    check(h == 0, "second new address must miss");
    if (COUNTER_MODE == 0) begin
        check(slot_count(20'hDEAD0) == -1, "mode 0: fresh line (count 1) should be the next victim");
        check(slot_count(20'hD0001) == 3,  "mode 0: slot 1 should survive");
    end else begin
        check(slot_count(20'hDEAD0) == 4,  "mode 1: line with inherited count 4 should survive");
        check(slot_count(20'hD0001) == -1, "mode 1: slot 1 (count 3) should be the next victim");
    end

    $display("----------------------------------------------");
    if (errors == 0) $display("ALL TESTS PASSED");
    else             $display("FAILED: %0d check(s) failed", errors);
    $display("----------------------------------------------");
    #20 $finish;
end

initial begin
    #200_000_000;
    $display("GLOBAL TIMEOUT");
    $finish;
end

endmodule
