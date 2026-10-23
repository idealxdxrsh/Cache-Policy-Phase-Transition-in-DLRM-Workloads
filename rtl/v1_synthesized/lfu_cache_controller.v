// ============================================================
//  lfu_cache_controller.v
//  Predictive Context LFU Cache Controller
//  Target: Datacenter GPU / Grace Hopper paradigm
//  Purpose: Architectural mitigation for sparse embedding
//           memory bottleneck in DLRMs
//  Author:  Sharanga HPC Research
// ============================================================

`timescale 1ns/1ps

module lfu_cache_controller #(
    parameter CACHE_DEPTH     = 16,    // Number of cache lines
    parameter ADDR_WIDTH      = 20,    // Embedding table address bits
    parameter VECTOR_WIDTH    = 128,   // Embedding vector width (bits)
    parameter COUNTER_WIDTH   = 8,     // Saturating frequency counter bits
    parameter TAG_WIDTH       = ADDR_WIDTH
)(
    input  wire                     clk,
    input  wire                     rst_n,

    // CPU/GPU request interface
    input  wire                     req_valid,
    input  wire [ADDR_WIDTH-1:0]    req_addr,
    output reg                      hit,
    output reg                      miss,
    output reg  [VECTOR_WIDTH-1:0]  rdata,

    // HBM/DRAM fill interface
    input  wire                     fill_valid,
    input  wire [ADDR_WIDTH-1:0]    fill_addr,
    input  wire [VECTOR_WIDTH-1:0]  fill_data,

    // Eviction / bypass output
    output reg                      evict_valid,
    output reg  [ADDR_WIDTH-1:0]    evict_addr,

    // Status
    output reg  [31:0]              hit_count,
    output reg  [31:0]              miss_count
);

    // -------------------------------------------------------
    // Cache storage arrays
    // -------------------------------------------------------
    reg [TAG_WIDTH-1:0]       tag_store   [0:CACHE_DEPTH-1];
    reg [VECTOR_WIDTH-1:0]    data_store  [0:CACHE_DEPTH-1];
    reg [COUNTER_WIDTH-1:0]   freq_cnt    [0:CACHE_DEPTH-1]; // 8-bit saturating counter
    reg                       valid_bits  [0:CACHE_DEPTH-1];

    // -------------------------------------------------------
    // Internal signals
    // -------------------------------------------------------
    integer i;
    reg [$clog2(CACHE_DEPTH)-1:0] hit_idx;
    reg [$clog2(CACHE_DEPTH)-1:0] lfu_idx;       // index of LFU victim
    reg [COUNTER_WIDTH-1:0]       lfu_min_val;
    reg                           hit_found;

    // -------------------------------------------------------
    // FSM States
    // -------------------------------------------------------
    localparam S_IDLE    = 2'b00;
    localparam S_LOOKUP  = 2'b01;
    localparam S_FILL    = 2'b10;
    localparam S_EVICT   = 2'b11;

    reg [1:0] state, next_state;

    // -------------------------------------------------------
    // State Register
    // -------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            hit_count  <= 0;
            miss_count <= 0;
            hit   <= 0;
            miss  <= 0;
            evict_valid <= 0;
            for (i = 0; i < CACHE_DEPTH; i = i + 1) begin
                valid_bits[i] <= 0;
                freq_cnt[i]   <= 0;
                tag_store[i]  <= 0;
                data_store[i] <= 0;
            end
        end else begin
            state <= next_state;
        end
    end

    // -------------------------------------------------------
    // Hit/Miss Detection + LFU Victim Selection (combinational)
    // -------------------------------------------------------
    always @(*) begin
        hit_found   = 1'b0;
        hit_idx     = 0;
        lfu_idx     = 0;
        lfu_min_val = {COUNTER_WIDTH{1'b1}}; // max value

        for (i = 0; i < CACHE_DEPTH; i = i + 1) begin
            // Tag match check
            if (valid_bits[i] && (tag_store[i] == req_addr)) begin
                hit_found = 1'b1;
                hit_idx   = i[$clog2(CACHE_DEPTH)-1:0];
            end
            // LFU victim: find minimum freq_cnt (prefer invalid slots)
            if (!valid_bits[i]) begin
                // Invalid slot — prefer as victim (freq=0 equivalent)
                if (lfu_min_val != 0) begin
                    lfu_min_val = 0;
                    lfu_idx = i[$clog2(CACHE_DEPTH)-1:0];
                end
            end else if (freq_cnt[i] < lfu_min_val) begin
                lfu_min_val = freq_cnt[i];
                lfu_idx     = i[$clog2(CACHE_DEPTH)-1:0];
            end
        end
    end

    // -------------------------------------------------------
    // FSM Next-State & Output Logic
    // -------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // reset handled above
        end else begin
            hit         <= 0;
            miss        <= 0;
            evict_valid <= 0;
            rdata       <= 0;

            case (state)
                S_IDLE: begin
                    if (req_valid) next_state <= S_LOOKUP;
                    else           next_state <= S_IDLE;
                end

                S_LOOKUP: begin
                    if (hit_found) begin
                        // ----- CACHE HIT -----
                        hit   <= 1'b1;
                        rdata <= data_store[hit_idx];
                        // Saturating increment of frequency counter
                        if (freq_cnt[hit_idx] != {COUNTER_WIDTH{1'b1}})
                            freq_cnt[hit_idx] <= freq_cnt[hit_idx] + 1;
                        hit_count  <= hit_count + 1;
                        next_state <= S_IDLE;
                    end else begin
                        // ----- CACHE MISS -----
                        miss       <= 1'b1;
                        miss_count <= miss_count + 1;
                        next_state <= S_EVICT;
                    end
                end

                S_EVICT: begin
                    // Signal eviction of LFU victim to upstream
                    if (valid_bits[lfu_idx]) begin
                        evict_valid <= 1'b1;
                        evict_addr  <= tag_store[lfu_idx];
                    end
                    // Invalidate victim slot
                    valid_bits[lfu_idx] <= 0;
                    freq_cnt[lfu_idx]   <= 0;
                    next_state <= S_FILL;
                end

                S_FILL: begin
                    // Wait for HBM fill response
                    if (fill_valid && (fill_addr == req_addr)) begin
                        tag_store[lfu_idx]  <= fill_addr;
                        data_store[lfu_idx] <= fill_data;
                        freq_cnt[lfu_idx]   <= 8'h01;   // initial count = 1
                        valid_bits[lfu_idx] <= 1'b1;
                        next_state <= S_IDLE;
                    end else begin
                        next_state <= S_FILL;
                    end
                end

                default: next_state <= S_IDLE;
            endcase
        end
    end

endmodule
