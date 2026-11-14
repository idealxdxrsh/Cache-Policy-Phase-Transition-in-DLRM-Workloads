// P13 on C2: synthesis/p11/tb_gls_slice.sv adapted for an Xcelium run of a Genus netlist with the library's own
// Verilog cell models (cadence/run_gls.csh). Same stimulus code and seed as P11 (and as tb_hitlog in P9/P10), so the
// RTL hit log must equal the P9 (v2) / P10 (v3) reference hit logs. Changes from P11, all in timing:
//  - timescale 1ps/1ps and a clock period of PERIOD_PS (default 800 = 0.8 ns, exact in ps); first rising edge at
//    PERIOD_PS/2, as in P11.
//  - inputs are driven IN_PS after each rising edge instead of on the falling edge; IN_PS = PERIOD_PS/2 (default)
//    gives the P11 timing, the SDF run uses the SDC input delay (0.2 x period).
//  - outputs are compared 1 ps before each rising edge instead of on it: the same values as in P11 (the outputs of
//    the previous edge), but no same-time-step race with cell-model flops in a zero-delay run, and settled values
//    in an SDF run.
//  - the netlist module is `GL_MODULE (the elaborated Genus name), so the netlist is compiled unchanged.
//  - +gl_hitlog=<file>: the netlist's own hit log in the same format, written at the compare point from the
//    netlist's outputs (index = netlist response count).
//  - with `GLS_SDF defined, delays.sdf in the run directory is annotated onto the netlist instance.
// Pass = all +nreq requests replayed, 0 mismatching cycles, 0 X cycles, netlist hit and response counts equal to
// the RTL's.
`timescale 1ps / 1ps
`ifndef GL_MODULE
`define GL_MODULE lfu_cache_controller_gl
`endif
module tb_gls_c2 #(parameter COUNTER_MODE = 0, parameter CACHE_DEPTH = 256, parameter SEED = 1,
                   parameter MAXREQ = 200000, parameter PERIOD_PS = 800, parameter IN_PS = PERIOD_PS / 2);
localparam AW = 20, VW = 128;
reg clk = 0, rst_n = 0;
event pre_rise;   // 1 ps before each rising edge: the compare point
initial forever begin #(PERIOD_PS / 2 - 1) -> pre_rise; #1 clk = 1; #(PERIOD_PS / 2) clk = 0; end
reg req_valid = 0, fill_valid = 0;
reg [AW-1:0] req_addr = 0;
reg [VW-1:0] fill_data = 0;
wire rv_r, hf_r, fr_r, rv_g, hf_g, fr_g;
wire [VW-1:0] rd_r, rd_g;
wire [AW-1:0] fa_r, fa_g;
lfu_cache_controller #(.CACHE_DEPTH(CACHE_DEPTH), .COUNTER_MODE(COUNTER_MODE)) rtl (
    .clk(clk), .rst_n(rst_n), .req_valid(req_valid), .req_addr(req_addr),
    .resp_valid(rv_r), .resp_data(rd_r), .hit_flag(hf_r), .fill_req(fr_r), .fill_addr(fa_r),
    .fill_valid(fill_valid), .fill_data(fill_data));
`GL_MODULE gl (
    .clk(clk), .rst_n(rst_n), .req_valid(req_valid), .req_addr(req_addr),
    .resp_valid(rv_g), .resp_data(rd_g), .hit_flag(hf_g), .fill_req(fr_g), .fill_addr(fa_g),
    .fill_valid(fill_valid), .fill_data(fill_data));
`ifdef GLS_SDF
initial $sdf_annotate("delays.sdf", gl);
`endif
integer cyc = 0, seed = SEED, d, k = 0, nreq = 0;
integer m_hf = 0, m_rv = 0, m_rd = 0, m_fr = 0, m_fa = 0, mism = 0, x_g = 0, x_r = 0;
integer n_resp = 0, n_hit = 0, n_miss = 0, g_resp = 0, g_hit = 0;
reg [AW-1:0] trace [0:MAXREQ-1];
reg [8*256-1:0] trace_file, hitlog_file, gl_hitlog_file;
integer hl = 0, glh = 0;
function integer rnd(input integer unused);
    rnd = $random(seed) & 32'h7fffffff;
endfunction
task next_drive;   // P11: @(negedge clk)
    begin @(posedge clk); #(IN_PS); end
endtask
always @(pre_rise) if (rst_n) begin
    cyc = cyc + 1;
    if (hf_r !== hf_g) m_hf = m_hf + 1;
    if (rv_r !== rv_g) m_rv = m_rv + 1;
    if (rd_r !== rd_g) m_rd = m_rd + 1;
    if (fr_r !== fr_g) m_fr = m_fr + 1;
    if (fa_r !== fa_g) m_fa = m_fa + 1;
    if ({hf_r, rv_r, rd_r, fr_r, fa_r} !== {hf_g, rv_g, rd_g, fr_g, fa_g}) begin
        mism = mism + 1;
        if (mism <= 10) $display("MISMATCH cycle %0d request %0d: rtl hf=%b rv=%b fr=%b fa=%h rd=%h | gl hf=%b rv=%b fr=%b fa=%h rd=%h",
                                 cyc, k, hf_r, rv_r, fr_r, fa_r, rd_r, hf_g, rv_g, fr_g, fa_g, rd_g);
    end
    if ((^{hf_g, rv_g, rd_g, fr_g, fa_g}) === 1'bx) begin
        x_g = x_g + 1;
        if (x_g <= 5) $display("X/Z ON NETLIST OUTPUT cycle %0d", cyc);
    end
    if ((^{hf_r, rv_r, rd_r, fr_r, fa_r}) === 1'bx) begin
        x_r = x_r + 1;
        if (x_r <= 5) $display("X/Z ON RTL OUTPUT cycle %0d", cyc);
    end
    if (rv_r) n_resp = n_resp + 1;
    if (rv_r && hf_r) n_hit = n_hit + 1;
    if (rv_r && !hf_r) n_miss = n_miss + 1;
    if (rv_g) begin
        if (glh) $fwrite(glh, "%0d %05h %0d\n", g_resp, trace[g_resp], hf_g);
        g_resp = g_resp + 1;
        if (hf_g) g_hit = g_hit + 1;
    end
    // progress, so a run that is stopped still records how far it got
    if (cyc % 50000 == 0)
        begin $display("cycles compared %0d, requests %0d, mismatches %0d (x_cycles netlist %0d, rtl %0d)", cyc, k, mism, x_g, x_r); $fflush; end
end
initial begin
    if (!$value$plusargs("trace=%s", trace_file)) $fatal(1, "needs +trace=<file>");
    if (!$value$plusargs("nreq=%d", nreq)) $fatal(1, "needs +nreq=<requests to replay>");
    $readmemh(trace_file, trace, 0, nreq - 1);
    if ($value$plusargs("hitlog=%s", hitlog_file)) hl = $fopen(hitlog_file, "w");
    if ($value$plusargs("gl_hitlog=%s", gl_hitlog_file)) glh = $fopen(gl_hitlog_file, "w");
    repeat (3) @(posedge clk);
    #(IN_PS);
    rst_n = 1;
    while (k < nreq) begin
        req_valid = 1; req_addr = trace[k];
        next_drive;
        req_valid = 0;
        while (!rv_r && !fr_r) next_drive;
        if (fr_r) begin
            d = rnd(0) % 4;
            repeat (d) next_drive;
            fill_valid = 1; fill_data = {rnd(0), rnd(0), rnd(0), rnd(0)};
            next_drive;
            fill_valid = 0;
            while (!rv_r) next_drive;
        end
        if (hl) $fwrite(hl, "%0d %05h %0d\n", k, trace[k], hf_r);
        k = k + 1;
    end
    @(posedge clk); #1;   // the last response is compared at the pre_rise event just before this edge
    $display("gls_c2 depth=%0d mode=%0d period_ps=%0d in_ps=%0d cycles=%0d requests=%0d responses=%0d hits=%0d misses=%0d gl_responses=%0d gl_hits=%0d mismatching_cycles=%0d hit_flag=%0d resp_valid=%0d resp_data=%0d fill_req=%0d fill_addr=%0d x_cycles_netlist=%0d x_cycles_rtl=%0d",
             CACHE_DEPTH, COUNTER_MODE, PERIOD_PS, IN_PS, cyc, k, n_resp, n_hit, n_miss, g_resp, g_hit, mism, m_hf, m_rv, m_rd, m_fr, m_fa, x_g, x_r);
    if (hl) $fclose(hl);
    if (glh) $fclose(glh);
    if (k == nreq && mism == 0 && x_g == 0 && x_r == 0 && g_hit == n_hit && g_resp == n_resp) $display("GLS SLICE LOCKSTEP PASSED");
    else                                                                                     $display("GLS SLICE LOCKSTEP FAILED");
    $finish;
end
endmodule
