// ============================================================
// LFU Cache Controller - v2 (256 lines, pipelined victim select)
// Author  : Adarsh (2023B1A31167G), BITS Pilani Goa
//
// STATUS: simulated with Icarus Verilog (see tb_lfu_cache.sv).
//         git tag rtl-v2-baseline: synthesized with Yosys 0.33
//         and OpenSTA on NanGate45, pre-layout, not TSMC; Fmax
//         165-215 MHz depending on depth and mode (see
//         results/P5/SUMMARY.md); does not meet 500 MHz; no
//         gate-level simulation.
//         P5b (Stage-B tree + address copies, commit 2a9f4ae):
//         Fmax 185.2-629.2 MHz (see results/P5b/SUMMARY.md).
//         This version (P5c: Stage-A and Stage-B trees + address
//         copies): same flow, NanGate45, pre-layout, not TSMC;
//         Fmax 199.4-626.1 MHz from the 1 GHz netlists; meets
//         500 MHz only at depth 16 (see results/P5c/SUMMARY.md);
//         no gate-level simulation.
//
// Changes vs v1 (rtl/v1):
//   - CACHE_DEPTH 16 -> 256
//   - COUNTER_WIDTH 8 -> 6 (saturates at 63)
//   - Victim selection split in two stages:
//       Stage A (registered, LOOKUP cycle): min of each group
//         (P5c: balanced reduction tree per group, log2(GSIZE)
//          levels; ties keep the lowest slot index)
//       Stage B (combinational, EVICT cycle): min across groups
//         (P5b: balanced reduction tree, log2(GROUPS) levels;
//          ties keep the lower-index side, as the serial loop did)
//   - P5b: per-group registered copies of the request address
//     drive the tag comparators and tag writes (same cycle)
//   - Hit detection ORs per-group first, then across groups
//   - P5d: hit index from a balanced priority tree (lowest
//     matching slot wins, as the serial loop did)
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
    if (GROUPS < 2 || (GROUPS & (GROUPS - 1)) != 0 || CACHE_DEPTH % GROUPS != 0
        || ((CACHE_DEPTH / GROUPS) & (CACHE_DEPTH / GROUPS - 1)) != 0) begin : BAD_GROUPS
        initial $fatal(1, "GROUPS=%0d must be a power of two >= 2 dividing CACHE_DEPTH=%0d into power-of-two groups",
                       GROUPS, CACHE_DEPTH);
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
// Per-group copies of req_addr_reg, loaded in the same cycle with the same value,
// so each copy drives only its group's GSIZE tag comparators and tag writes.
// keep: stops synthesis from merging the identical registers back into one.
(* keep *) reg [ADDR_WIDTH-1:0] req_addr_grp [0:GROUPS-1];

// ---- hit detection (per-group OR, then OR of groups) --------
wire [CACHE_DEPTH-1:0] match;
wire [GROUPS-1:0]      group_hit;
wire                   hit_detected;
genvar g;
generate
    for (g = 0; g < CACHE_DEPTH; g = g + 1) begin : TAG_CMP
        assign match[g] = valid_bits[g] && (tag_store[g] == req_addr_grp[g / GSIZE]);
    end
    for (g = 0; g < GROUPS; g = g + 1) begin : GRP_OR
        assign group_hit[g] = |match[g*GSIZE +: GSIZE];
    end
endgenerate
assign hit_detected = |group_hit;

// P5d: hit_idx from a balanced priority tree (log2(CACHE_DEPTH)
// levels) instead of a serial loop. Heap order: slot i is leaf
// CACHE_DEPTH-1+i, node n has children 2n+1 (left, lower slots) and
// 2n+2. A node takes the right child only if the left subtree has
// no match and the right one has, so hit_idx is the lowest matching
// slot, and 0 when nothing matches, exactly like the former loop.
// It does not rely on at most one match. That invariant does hold:
// tags are written only at reset and in FILL, valid bits are set
// only in FILL, FILL follows only a LOOKUP miss on an address held
// since IDLE, and there is no flush path (see results/P5d/SUMMARY.md).
localparam HNODES = 2*CACHE_DEPTH - 1;
wire [HNODES-1:0]           h_any;
wire [HNODES*IDX_WIDTH-1:0] h_idx;
generate
    for (g = 0; g < CACHE_DEPTH; g = g + 1) begin : HIT_LEAF
        assign h_any[CACHE_DEPTH-1+g] = match[g];
        assign h_idx[(CACHE_DEPTH-1+g)*IDX_WIDTH +: IDX_WIDTH] = g;
    end
    for (g = 0; g < CACHE_DEPTH-1; g = g + 1) begin : HIT_NODE
        wire h_take_r = !h_any[2*g+1] && h_any[2*g+2];
        assign h_any[g] = h_any[2*g+1] | h_any[2*g+2];
        assign h_idx[g*IDX_WIDTH +: IDX_WIDTH] = h_take_r ? h_idx[(2*g+2)*IDX_WIDTH +: IDX_WIDTH]
                                                          : h_idx[(2*g+1)*IDX_WIDTH +: IDX_WIDTH];
    end
endgenerate
wire [IDX_WIDTH-1:0] hit_idx = h_idx[IDX_WIDTH-1:0];

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

// Stage A: registered during LOOKUP on a miss.
// P5c: one balanced min-reduction tree per group, same heap order
// and tie rule as Stage B: slot s of group g is leaf GSIZE-1+s; a
// node takes the right child only if it is strictly smaller, so
// ties resolve to the lowest slot index, like the former serial loop.
localparam ANODES = 2*GSIZE - 1;
reg  [IDX_WIDTH-1:0]        stageA_min [0:GROUPS-1];
wire [GROUPS*IDX_WIDTH-1:0] stageA_comb;
genvar s;
generate
    for (g = 0; g < GROUPS; g = g + 1) begin : GRP_TREE
        wire [ANODES*EW-1:0]        a_val;
        wire [ANODES*IDX_WIDTH-1:0] a_idx;
        for (s = 0; s < GSIZE; s = s + 1) begin : A_LEAF
            assign a_val[(GSIZE-1+s)*EW +: EW] = eff(valid_bits[g*GSIZE+s], freq_cnt[g*GSIZE+s]);
            assign a_idx[(GSIZE-1+s)*IDX_WIDTH +: IDX_WIDTH] = g*GSIZE + s;
        end
        for (s = 0; s < GSIZE-1; s = s + 1) begin : A_NODE
            wire [EW-1:0] a_lv = a_val[(2*s+1)*EW +: EW];
            wire [EW-1:0] a_rv = a_val[(2*s+2)*EW +: EW];
            wire a_take_r = a_rv < a_lv;
            assign a_val[s*EW +: EW] = a_take_r ? a_rv : a_lv;
            assign a_idx[s*IDX_WIDTH +: IDX_WIDTH] = a_take_r ? a_idx[(2*s+2)*IDX_WIDTH +: IDX_WIDTH]
                                                              : a_idx[(2*s+1)*IDX_WIDTH +: IDX_WIDTH];
        end
        assign stageA_comb[g*IDX_WIDTH +: IDX_WIDTH] = a_idx[IDX_WIDTH-1:0];
    end
endgenerate

integer sa;
always @(posedge clk) begin
    if (state == LOOKUP && !hit_detected) begin
        for (sa = 0; sa < GROUPS; sa = sa + 1)
            stageA_min[sa] <= stageA_comb[sa*IDX_WIDTH +: IDX_WIDTH];
    end
end

// Stage B: combinational, consumed in the EVICT cycle.
// Balanced min-reduction tree in heap order: node n has children
// 2n+1 (left, lower group indices) and 2n+2 (right); group g is
// leaf GROUPS-1+g; node 0 is the root. A node takes the right
// child only if it is strictly smaller, so ties resolve to the
// lowest group index, exactly like the former serial loop.
localparam NODES = 2*GROUPS - 1;
wire [NODES*EW-1:0]        tree_val;
wire [NODES*IDX_WIDTH-1:0] tree_idx;
generate
    for (g = 0; g < GROUPS; g = g + 1) begin : TREE_LEAF
        assign tree_val[(GROUPS-1+g)*EW +: EW] = eff(valid_bits[stageA_min[g]], freq_cnt[stageA_min[g]]);
        assign tree_idx[(GROUPS-1+g)*IDX_WIDTH +: IDX_WIDTH] = stageA_min[g];
    end
    for (g = 0; g < GROUPS-1; g = g + 1) begin : TREE_NODE
        wire [EW-1:0] lv = tree_val[(2*g+1)*EW +: EW];
        wire [EW-1:0] rv = tree_val[(2*g+2)*EW +: EW];
        wire take_r = rv < lv;
        assign tree_val[g*EW +: EW] = take_r ? rv : lv;
        assign tree_idx[g*IDX_WIDTH +: IDX_WIDTH] = take_r ? tree_idx[(2*g+2)*IDX_WIDTH +: IDX_WIDTH]
                                                           : tree_idx[(2*g+1)*IDX_WIDTH +: IDX_WIDTH];
    end
endgenerate
wire [IDX_WIDTH-1:0] victim_comb = tree_idx[IDX_WIDTH-1:0];

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

integer ag;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        for (ag = 0; ag < GROUPS; ag = ag + 1) req_addr_grp[ag] <= {ADDR_WIDTH{1'b0}};
    else if (state == IDLE && req_valid)
        for (ag = 0; ag < GROUPS; ag = ag + 1) req_addr_grp[ag] <= req_addr;
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
                for (i = 0; i < CACHE_DEPTH; i = i + 1)
                    if (victim_reg == i) tag_store[i] <= req_addr_grp[i / GSIZE];
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
