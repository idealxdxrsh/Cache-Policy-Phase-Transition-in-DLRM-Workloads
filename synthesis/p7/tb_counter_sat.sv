// P7: counter-saturation check for the P5f lockstep runs. RTL only (rtl/v2, tag rtl-v2-final), driven by exactly
// the stimulus of synthesis/p5f/tb_gls_lockstep.sv (same seed, same falling-edge code, copied by
// synthesis/p7/run_counter_sat.sh; the response/hit/miss/fill counts printed here must equal the P5f lockstep logs,
// which shows the stimulus is identical). Reports the largest counter value reached, the cycles in which any valid
// line's counter is at its maximum (2^COUNTER_WIDTH - 1), and the increments the RTL suppressed because the counter
// was already at that maximum (a hit in LOOKUP, or a mode-1 FILL into a slot at the maximum).
`timescale 1ns / 1ps
module tb_counter_sat #(parameter COUNTER_MODE = 0, parameter CACHE_DEPTH = 256,
                        parameter CYCLES = 200000, parameter SEED = 1);
localparam AW = 20, VW = 128, CW = 6, CMAX = (1 << CW) - 1;
localparam [1:0] LOOKUP = 2'b01, FILL = 2'b11;
reg clk = 0, rst_n = 0;
always #0.5 clk = ~clk;
reg req_valid = 0, fill_valid = 0;
reg [AW-1:0] req_addr = 0;
reg [VW-1:0] fill_data = 0;
wire rv_r, hf_r, fr_r;
wire [VW-1:0] rd_r;
wire [AW-1:0] fa_r;
lfu_cache_controller #(.CACHE_DEPTH(CACHE_DEPTH), .COUNTER_MODE(COUNTER_MODE)) rtl (
    .clk(clk), .rst_n(rst_n), .req_valid(req_valid), .req_addr(req_addr),
    .resp_valid(rv_r), .resp_data(rd_r), .hit_flag(hf_r), .fill_req(fr_r), .fill_addr(fa_r),
    .fill_valid(fill_valid), .fill_data(fill_data));
integer cyc = 0, seed = SEED, pool, d, k, mx, maxc = 0, sat_cycles = 0, sat_lines_max = 0, nsat, sup_hit = 0, sup_fill = 0;
integer n_resp = 0, n_hit = 0, n_miss = 0, n_fill = 0;
function integer rnd(input integer unused);
    rnd = $random(seed) & 32'h7fffffff;
endfunction
always @(posedge clk) if (rst_n) begin
    cyc = cyc + 1;
    mx = 0; nsat = 0;
    for (k = 0; k < CACHE_DEPTH; k = k + 1)
        if (rtl.valid_bits[k]) begin
            if (rtl.freq_cnt[k] > mx) mx = rtl.freq_cnt[k];
            if (rtl.freq_cnt[k] == CMAX) nsat = nsat + 1;
        end
    if (mx > maxc) maxc = mx;
    if (nsat > 0) sat_cycles = sat_cycles + 1;
    if (nsat > sat_lines_max) sat_lines_max = nsat;
    if (rtl.state == LOOKUP && rtl.hit_detected && rtl.freq_cnt[rtl.hit_idx] == CMAX) sup_hit = sup_hit + 1;
    if (COUNTER_MODE == 1 && rtl.state == FILL && fill_valid && rtl.freq_cnt[rtl.victim_reg] == CMAX) sup_fill = sup_fill + 1;
    if (rv_r) n_resp = n_resp + 1;
    if (rv_r && hf_r) n_hit = n_hit + 1;
    if (rv_r && !hf_r) n_miss = n_miss + 1;
    if (fr_r) n_fill = n_fill + 1;
end
// Stimulus on the falling edge, as in synthesis/p5b/tb_lockstep.sv.
initial begin
    repeat (3) @(negedge clk);
    rst_n = 1;
    while (cyc < CYCLES) begin
        @(negedge clk);
        pool = (rnd(0) % 4 == 0) ? 2 * CACHE_DEPTH : CACHE_DEPTH / 4 + 1;
        req_valid = (rnd(0) % 3) != 0;
        req_addr = 20'h40000 + (rnd(0) % pool);
        if (fr_r) begin
            d = rnd(0) % 4;
            req_valid = 0;
            repeat (d) @(negedge clk);
            fill_valid = 1; fill_data = {rnd(0), rnd(0), rnd(0), rnd(0)};
            @(negedge clk);
            fill_valid = 0;
        end
    end
    $display("counter_sat depth=%0d mode=%0d cycles=%0d responses=%0d hits=%0d misses=%0d fill_reqs=%0d counter_max_value=%0d max_reached=%0d cycles_with_a_line_at_max=%0d most_lines_at_max=%0d suppressed_hit_increments=%0d suppressed_fill_increments=%0d",
             CACHE_DEPTH, COUNTER_MODE, cyc, n_resp, n_hit, n_miss, n_fill, CMAX, maxc, sat_cycles, sat_lines_max, sup_hit, sup_fill);
    $finish;
end
endmodule
