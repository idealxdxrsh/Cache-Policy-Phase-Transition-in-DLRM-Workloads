// ============================================================
// LFU Cache Controller - v2 (256 lines, pipelined victim select)
// Author  : Adarsh (2023B1A31167G), BITS Pilani Goa
//
// STATUS: simulated with Icarus Verilog (see tb_lfu_cache.sv).
//         NOT yet synthesized. Fmax / area figures in the docs
//         for this version are PROJECTIONS, not measurements.
//
// Changes vs v1 (rtl/v1):
//   - CACHE_DEPTH 16 -> 256
//   - COUNTER_WIDTH 8 -> 6 (saturates at 63)
//   - Victim selection split in two stages:
//       Stage A (registered, LOOKUP cycle): min of each group
//       Stage B (combinational, EVICT cycle): min across groups
//   - Hit detection ORs per-group first, then across groups
//
// Counter semantics, selected by COUNTER_MODE:
//   0 (default): count is set to 1 when a tag is installed
//                (reset-on-eviction LFU).
//   1          : original v2 behaviour. freq_cnt is stored per
//                SLOT and NOT cleared on eviction; a new tag
//                continues from the slot's old count (+1).
//   2          : address-indexed history. NOT implemented; the
//                scheme is pending Prof. Mane. Elaboration fails.
//   Neither 0 nor 1 is per-ADDRESS history.
// ============================================================
`timescale 1ns / 1ps

module lfu_cache_controller #(
    parameter CACHE_DEPTH   = 256,
    parameter ADDR_WIDTH    = 20,
    parameter VECTOR_WIDTH  = 128,
    parameter COUNTER_WIDTH = 6,
    parameter GROUPS        = 16,
    parameter COUNTER_MODE  = 0,
    parameter IDX_WIDTH     = $clog2(CACHE_DEPTH)
)(
    input  wire                     clk,
    input  wire                     rst_n,

    input  wire                     req_valid,
    input  wire [ADDR_WIDTH-1:0]    req_addr,

    output reg                      resp_valid,
    output reg  [VECTOR_WIDTH-1:0]  resp_data,
    output reg                      hit_flag,

    output reg                      fill_req,
    output reg  [ADDR_WIDTH-1:0]    fill_addr,
    input  wire                     fill_valid,
    input  wire [VECTOR_WIDTH-1:0]  fill_data
);

localparam GSIZE = CACHE_DEPTH / GROUPS;
localparam EW    = COUNTER_WIDTH + 1;      // effective-count width

generate
    if (COUNTER_MODE != 0 && COUNTER_MODE != 1) begin : BAD_COUNTER_MODE
        initial $fatal(1, "COUNTER_MODE=%0d not supported (0 or 1; 2 is pending)", COUNTER_MODE);
    end
endgenerate

// ---- storage ------------------------------------------------
reg [ADDR_WIDTH-1:0]    tag_store  [0:CACHE_DEPTH-1];
reg [VECTOR_WIDTH-1:0]  data_store [0:CACHE_DEPTH-1];
reg [COUNTER_WIDTH-1:0] freq_cnt   [0:CACHE_DEPTH-1];
reg                     valid_bits [0:CACHE_DEPTH-1];

// ---- FSM ----------------------------------------------------
localparam IDLE = 2'b00, LOOKUP = 2'b01, EVICT = 2'b10, FILL = 2'b11;
reg [1:0] state, next_state;
reg [ADDR_WIDTH-1:0] req_addr_reg;

// ---- hit detection (per-group OR, then OR of groups) --------
wire [CACHE_DEPTH-1:0] match;
wire [GROUPS-1:0]      group_hit;
wire                   hit_detected;
genvar g;
generate
    for (g = 0; g < CACHE_DEPTH; g = g + 1) begin : TAG_CMP
        assign match[g] = valid_bits[g] && (tag_store[g] == req_addr_reg);
    end
    for (g = 0; g < GROUPS; g = g + 1) begin : GRP_OR
        assign group_hit[g] = |match[g*GSIZE +: GSIZE];
    end
endgenerate
assign hit_detected = |group_hit;

integer hi;
reg [IDX_WIDTH-1:0] hit_idx;
always @(*) begin
    hit_idx = {IDX_WIDTH{1'b0}};
    for (hi = CACHE_DEPTH-1; hi >= 0; hi = hi - 1)
        if (match[hi]) hit_idx = hi[IDX_WIDTH-1:0];
end

// ---- victim selection ---------------------------------------
// Effective count: empty slot = 0 (always preferred as victim),
// valid slot = freq+1. Ties resolve to the lowest index.
function [EW-1:0] eff;
    input v;
    input [COUNTER_WIDTH-1:0] c;
    begin
        eff = v ? ({1'b0, c} + {{(EW-1){1'b0}}, 1'b1}) : {EW{1'b0}};
    end
endfunction

// Stage A: registered during LOOKUP on a miss
reg [IDX_WIDTH-1:0] stageA_min [0:GROUPS-1];
integer sa, sm;
reg [IDX_WIDTH-1:0] a_idx;
reg [EW-1:0]        a_best, a_cur;
always @(posedge clk) begin
    if (state == LOOKUP && !hit_detected) begin
        for (sa = 0; sa < GROUPS; sa = sa + 1) begin
            a_idx  = sa * GSIZE;
            a_best = eff(valid_bits[sa*GSIZE], freq_cnt[sa*GSIZE]);
            for (sm = sa*GSIZE + 1; sm < (sa+1)*GSIZE; sm = sm + 1) begin
                a_cur = eff(valid_bits[sm], freq_cnt[sm]);
                if (a_cur < a_best) begin
                    a_best = a_cur;
                    a_idx  = sm;
                end
            end
            stageA_min[sa] <= a_idx;
        end
    end
end

// Stage B: combinational, consumed in the EVICT cycle
integer sb;
reg [IDX_WIDTH-1:0] victim_comb;
reg [EW-1:0]        b_best, b_cur;
always @(*) begin
    victim_comb = stageA_min[0];
    b_best = eff(valid_bits[stageA_min[0]], freq_cnt[stageA_min[0]]);
    for (sb = 1; sb < GROUPS; sb = sb + 1) begin
        b_cur = eff(valid_bits[stageA_min[sb]], freq_cnt[stageA_min[sb]]);
        if (b_cur < b_best) begin
            b_best      = b_cur;
            victim_comb = stageA_min[sb];
        end
    end
end

reg [IDX_WIDTH-1:0] victim_reg;   // held for the FILL cycle

// ---- FSM ----------------------------------------------------
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) state <= IDLE;
    else        state <= next_state;
end

always @(posedge clk or negedge rst_n) begin
    if (!rst_n)                          req_addr_reg <= {ADDR_WIDTH{1'b0}};
    else if (state == IDLE && req_valid) req_addr_reg <= req_addr;
end

always @(*) begin
    next_state = state;
    case (state)
        IDLE:   if (req_valid)    next_state = LOOKUP;
        LOOKUP: next_state = hit_detected ? IDLE : EVICT;
        EVICT:  next_state = FILL;
        FILL:   if (fill_valid)   next_state = IDLE;
        default:                  next_state = IDLE;
    endcase
end

// ---- datapath -----------------------------------------------
integer i;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        resp_valid <= 1'b0;
        hit_flag   <= 1'b0;
        fill_req   <= 1'b0;
        fill_addr  <= {ADDR_WIDTH{1'b0}};
        resp_data  <= {VECTOR_WIDTH{1'b0}};
        victim_reg <= {IDX_WIDTH{1'b0}};
        for (i = 0; i < CACHE_DEPTH; i = i + 1) begin
            valid_bits[i] <= 1'b0;
            freq_cnt[i]   <= {COUNTER_WIDTH{1'b0}};
            tag_store[i]  <= {ADDR_WIDTH{1'b0}};
            data_store[i] <= {VECTOR_WIDTH{1'b0}};
        end
    end else begin
        resp_valid <= 1'b0;
        hit_flag   <= 1'b0;
        fill_req   <= 1'b0;

        case (state)
            LOOKUP: if (hit_detected) begin
                hit_flag   <= 1'b1;
                resp_valid <= 1'b1;
                resp_data  <= data_store[hit_idx];
                if (freq_cnt[hit_idx] != {COUNTER_WIDTH{1'b1}})
                    freq_cnt[hit_idx] <= freq_cnt[hit_idx] + 1'b1;
            end

            EVICT: begin
                victim_reg                <= victim_comb;
                valid_bits[victim_comb]   <= 1'b0;
                // freq_cnt[victim_comb] not touched here; FILL sets it
                fill_req                  <= 1'b1;
                fill_addr                 <= req_addr_reg;
            end

            FILL: if (fill_valid) begin
                tag_store[victim_reg]   <= req_addr_reg;
                data_store[victim_reg]  <= fill_data;
                valid_bits[victim_reg]  <= 1'b1;
                if (COUNTER_MODE == 0)
                    freq_cnt[victim_reg] <= {{(COUNTER_WIDTH-1){1'b0}}, 1'b1};
                else if (freq_cnt[victim_reg] != {COUNTER_WIDTH{1'b1}})
                    freq_cnt[victim_reg] <= freq_cnt[victim_reg] + 1'b1;
                resp_data  <= fill_data;
                resp_valid <= 1'b1;
            end

            default: ;
        endcase
    end
end

endmodule
