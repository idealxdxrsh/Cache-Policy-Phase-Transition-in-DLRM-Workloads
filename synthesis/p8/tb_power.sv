// P8 power stimulus: zero-delay simulation of the controller (netlist module lfu_cache_controller_gl, or the RTL with
// +define+USE_RTL), clock 2 ns (500 MHz). Instance name `gl` in both cases, so the VCD scope is tb_power/gl.
// STIM = 0: the random stimulus of synthesis/p5f/tb_gls_lockstep.sv (same seed and code; fill handshake keyed on the
//           controller's own fill_req).
// STIM = 1: replay of a request trace (+trace=<file>, one hex address per line): one request outstanding; the next
//           request is presented on the falling edge after the response; on a miss the fill arrives 0-3 cycles after
//           fill_req (random, seed SEED).
// Fill data: random ($random, seed SEED) in both cases; real embedding vectors are not random.
// Warm-up WARM cycles (not recorded), then WIN cycles recorded into the VCD (+vcd=<file>; written only if given).
// Reported: cycles, requests issued (STIM 1), responses, hits, misses, for the whole run and for the window, the
// window's first and last request index (STIM 1) and the window's start and end time in ps.
`timescale 1ns / 1ps
module tb_power #(parameter COUNTER_MODE = 0, parameter CACHE_DEPTH = 256, parameter STIM = 0,
                  parameter WARM = 20000, parameter WIN = 10000, parameter SEED = 1, parameter MAXREQ = 200000);
localparam AW = 20, VW = 128;
reg clk = 0, rst_n = 0;
always #1 clk = ~clk;
reg req_valid = 0, fill_valid = 0;
reg [AW-1:0] req_addr = 0;
reg [VW-1:0] fill_data = 0;
wire rv, hf, fr;
wire [VW-1:0] rd;
wire [AW-1:0] fa;
`ifdef USE_RTL
lfu_cache_controller #(.CACHE_DEPTH(CACHE_DEPTH), .COUNTER_MODE(COUNTER_MODE)) gl (
`else
lfu_cache_controller_gl gl (
`endif
    .clk(clk), .rst_n(rst_n), .req_valid(req_valid), .req_addr(req_addr),
    .resp_valid(rv), .resp_data(rd), .hit_flag(hf), .fill_req(fr), .fill_addr(fa),
    .fill_valid(fill_valid), .fill_data(fill_data));
integer cyc = 0, seed = SEED, pool, d, k = 0, nreq = 0, k_first = -1, k_last = -1;
integer n_resp = 0, n_hit = 0, n_miss = 0, w_resp = 0, w_hit = 0, w_miss = 0, w_req = 0, x_out = 0;
integer q_resp = 0, q_hit = 0;   // STIM 1: responses and hits of the requests issued in the window
reg cur_in_win = 0;
reg [AW-1:0] trace [0:MAXREQ-1];
reg [8*256-1:0] vcd_file, trace_file;
reg dumping = 0;
time t_begin = 0, t_end = 0;
function integer rnd(input integer unused);
    rnd = $random(seed) & 32'h7fffffff;
endfunction
wire in_win = cyc > WARM && cyc <= WARM + WIN;
always @(posedge clk) if (rst_n) begin
    cyc = cyc + 1;
    if (rv) begin n_resp = n_resp + 1; if (in_win) w_resp = w_resp + 1; end
    if (rv && hf) begin n_hit = n_hit + 1; if (in_win) w_hit = w_hit + 1; end
    if (rv && !hf) begin n_miss = n_miss + 1; if (in_win) w_miss = w_miss + 1; end
    if ((^{hf, rv, rd, fr, fa}) === 1'bx) x_out = x_out + 1;
    if (cyc == WARM && $value$plusargs("vcd=%s", vcd_file)) begin
        t_begin = $time;
        $dumpfile(vcd_file);
        $dumpvars(0, tb_power.gl);
        dumping = 1;
    end
    if (cyc == WARM + WIN) begin
        t_end = $time;
        if (dumping) $dumpoff;
    end
end
task issue(input integer idx);
    begin
        req_valid = 1; req_addr = trace[idx];
        cur_in_win = cyc >= WARM && cyc < WARM + WIN;
        if (cur_in_win) begin
            w_req = w_req + 1;
            if (k_first < 0) k_first = idx;
            k_last = idx;
        end
    end
endtask
initial begin
    if (STIM == 1) begin
        if (!$value$plusargs("trace=%s", trace_file)) $fatal(1, "STIM=1 needs +trace=<file>");
        if (!$value$plusargs("nreq=%d", nreq)) $fatal(1, "STIM=1 needs +nreq=<requests in the file>");
        $readmemh(trace_file, trace, 0, nreq - 1);
    end
    repeat (3) @(negedge clk);
    rst_n = 1;
    while (cyc < WARM + WIN) begin
        if (STIM == 0) begin
            @(negedge clk);
            pool = (rnd(0) % 4 == 0) ? 2 * CACHE_DEPTH : CACHE_DEPTH / 4 + 1;
            req_valid = (rnd(0) % 3) != 0;
            req_addr = 20'h40000 + (rnd(0) % pool);
            if (fr) begin
                d = rnd(0) % 4;
                req_valid = 0;
                repeat (d) @(negedge clk);
                fill_valid = 1; fill_data = {rnd(0), rnd(0), rnd(0), rnd(0)};
                @(negedge clk);
                fill_valid = 0;
            end
        end else begin
            if (k >= nreq) $fatal(1, "trace exhausted after %0d requests at cycle %0d", k, cyc);
            issue(k);
            @(negedge clk);
            req_valid = 0;
            while (!rv && !fr) @(negedge clk);
            if (fr) begin
                d = rnd(0) % 4;
                repeat (d) @(negedge clk);
                fill_valid = 1; fill_data = {rnd(0), rnd(0), rnd(0), rnd(0)};
                @(negedge clk);
                fill_valid = 0;
                while (!rv) @(negedge clk);
            end
            if (cur_in_win) begin q_resp = q_resp + 1; if (hf) q_hit = q_hit + 1; end   // this request's response
            k = k + 1;
        end
    end
    @(posedge clk); #0.1;   // count the last response (responses are counted on the edge after they appear)
    $display("p8_power depth=%0d mode=%0d stim=%0d warm=%0d win=%0d cycles=%0d requests=%0d responses=%0d hits=%0d misses=%0d win_requests=%0d win_responses=%0d win_hits=%0d win_misses=%0d win_first_req=%0d win_last_req=%0d winreq_responses=%0d winreq_hits=%0d t_begin_ps=%0d t_end_ps=%0d x_cycles=%0d",
             CACHE_DEPTH, COUNTER_MODE, STIM, WARM, WIN, cyc, k, n_resp, n_hit, n_miss, w_req, w_resp, w_hit, w_miss,
             k_first, k_last, q_resp, q_hit, t_begin * 1000, t_end * 1000, x_out);
    $finish;
end
endmodule
