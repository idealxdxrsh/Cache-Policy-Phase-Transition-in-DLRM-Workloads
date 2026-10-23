`timescale 1ns / 1ps

module lfu_cache_controller #(
    parameter ADDR_WIDTH = 32,      // 32-bit embedding indices
    parameter DATA_WIDTH = 512,     // 64 FP16/FP32 values per embedding vector
    parameter CACHE_DEPTH = 16,     // Number of concurrent hot vectors stored
    parameter FREQ_WIDTH = 8        // 8-bit saturation counter for LFU
)(
    input  wire                   clk,
    input  wire                   rst_n,

    // Interface from Compute Units (Tensor Cores / SMs)
    input  wire                   req_valid,
    input  wire [ADDR_WIDTH-1:0]  req_addr,
    output reg                    req_ready,

    // Interface to Compute Units (Responses)
    output reg                    resp_valid,
    output reg  [DATA_WIDTH-1:0]  resp_data,

    // Interface to Main Memory (HBM / Host DRAM)
    output reg                    mem_req_valid,
    output reg  [ADDR_WIDTH-1:0]  mem_req_addr,
    input  wire                   mem_req_ready,
    input  wire                   mem_resp_valid,
    input  wire [DATA_WIDTH-1:0]  mem_resp_data
);

    // -------------------------------------------------------------------------
    // 1. Cache Memory Arrays
    // -------------------------------------------------------------------------
    reg [DATA_WIDTH-1:0] cache_data [0:CACHE_DEPTH-1];
    reg [ADDR_WIDTH-1:0] cache_tags [0:CACHE_DEPTH-1];
    reg                  valid_bits [0:CACHE_DEPTH-1];
    reg [FREQ_WIDTH-1:0] freq_count [0:CACHE_DEPTH-1];

    // -------------------------------------------------------------------------
    // 2. FSM State Encoding
    // -------------------------------------------------------------------------
    localparam IDLE       = 3'b000;
    localparam TAG_CHECK  = 3'b001;
    localparam EVICT_LFU  = 3'b010;
    localparam FETCH_MEM  = 3'b011;
    localparam ALLOCATE   = 3'b100;

    reg [2:0] current_state, next_state;

    // Internal routing registers
    reg [ADDR_WIDTH-1:0] latched_req_addr;
    reg [$clog2(CACHE_DEPTH)-1:0] target_idx; // Index for hit or eviction
    reg hit_detected;

    // -------------------------------------------------------------------------
    // 3. Combinational Logic: Hit Detection & LFU Victim Selection
    // -------------------------------------------------------------------------
    integer i;
    reg [$clog2(CACHE_DEPTH)-1:0] lfu_idx;
    reg [FREQ_WIDTH-1:0] min_freq;
    reg hit_flag;
    reg [$clog2(CACHE_DEPTH)-1:0] hit_index;

    always @(*) begin
        // Default assignments
        hit_flag = 1'b0;
        hit_index = 0;
        min_freq = {FREQ_WIDTH{1'b1}}; // Max value
        lfu_idx = 0;

        for (i = 0; i < CACHE_DEPTH; i = i + 1) begin
            // Check for Hit
            if (valid_bits[i] && (cache_tags[i] == latched_req_addr)) begin
                hit_flag = 1'b1;
                hit_index = i;
            end
            
            // Find minimum frequency for eviction (ignoring invalid lines as they are freq=0)
            if (!valid_bits[i]) begin
                min_freq = 0;
                lfu_idx = i; // Empty slots get priority for eviction/filling
            end else if (freq_count[i] <= min_freq) begin
                min_freq = freq_count[i];
                lfu_idx = i;
            end
        end
    end

    // -------------------------------------------------------------------------
    // 4. Sequential Logic: FSM State Transition
    // -------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_state <= IDLE;
        end else begin
            current_state <= next_state;
        end
    end

    // -------------------------------------------------------------------------
    // 5. FSM Next State & Output Logic
    // -------------------------------------------------------------------------
    integer j;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset all arrays and outputs
            for (j = 0; j < CACHE_DEPTH; j = j + 1) begin
                valid_bits[j] <= 1'b0;
                freq_count[j] <= 0;
            end
            req_ready <= 1'b1;
            resp_valid <= 1'b0;
            mem_req_valid <= 1'b0;
            next_state <= IDLE;
        end else begin
            // Default pulse resets
            resp_valid <= 1'b0;
            
            case (current_state)
                IDLE: begin
                    req_ready <= 1'b1;
                    if (req_valid) begin
                        latched_req_addr <= req_addr;
                        req_ready <= 1'b0; // Block new requests
                        next_state <= TAG_CHECK;
                    end
                end

                TAG_CHECK: begin
                    if (hit_flag) begin
                        // CACHE HIT
                        resp_data <= cache_data[hit_index];
                        resp_valid <= 1'b1;
                        
                        // Saturating frequency counter increment
                        if (freq_count[hit_index] != {FREQ_WIDTH{1'b1}})
                            freq_count[hit_index] <= freq_count[hit_index] + 1;
                            
                        next_state <= IDLE;
                    end else begin
                        // CACHE MISS
                        target_idx <= lfu_idx; // Lock in the victim index
                        next_state <= EVICT_LFU;
                    end
                end

                EVICT_LFU: begin
                    // In a Write-Back cache, we would write dirty data back to memory here.
                    // Since DLRM embeddings are Read-Only during inference, we just overwrite.
                    mem_req_addr <= latched_req_addr;
                    mem_req_valid <= 1'b1;
                    
                    if (mem_req_ready) begin
                        next_state <= FETCH_MEM;
                    end
                end

                FETCH_MEM: begin
                    // Keep request high until accepted, then wait for response
                    if (mem_req_ready) mem_req_valid <= 1'b0; 
                    
                    if (mem_resp_valid) begin
                        next_state <= ALLOCATE;
                    end
                end

                ALLOCATE: begin
                    // Write the new embedding vector into the cache
                    cache_data[target_idx] <= mem_resp_data;
                    cache_tags[target_idx] <= latched_req_addr;
                    valid_bits[target_idx] <= 1'b1;
                    freq_count[target_idx] <= 1; // Initialize frequency
                    
                    // Forward data directly to compute units
                    resp_data <= mem_resp_data;
                    resp_valid <= 1'b1;
                    
                    next_state <= IDLE;
                end

                default: next_state <= IDLE;
            endcase
        end
    end

endmodule