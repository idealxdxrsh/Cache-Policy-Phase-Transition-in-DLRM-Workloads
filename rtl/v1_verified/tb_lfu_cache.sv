`timescale 1ns / 1ps

module tb_lfu_cache();

    // -------------------------------------------------------------------------
    // Parameters (Matching the RTL)
    // -------------------------------------------------------------------------
    localparam ADDR_WIDTH = 32;
    localparam DATA_WIDTH = 512;
    localparam CACHE_DEPTH = 16;
    localparam FREQ_WIDTH = 8;
    localparam CLK_PERIOD = 10; // 100MHz Clock

    // -------------------------------------------------------------------------
    // Signals
    // -------------------------------------------------------------------------
    reg                   clk;
    reg                   rst_n;

    // Compute Unit Interface
    reg                   req_valid;
    reg  [ADDR_WIDTH-1:0] req_addr;
    wire                  req_ready;
    wire                  resp_valid;
    wire [DATA_WIDTH-1:0] resp_data;

    // Main Memory Interface (Simulated HBM)
    wire                  mem_req_valid;
    wire [ADDR_WIDTH-1:0] mem_req_addr;
    reg                   mem_req_ready;
    reg                   mem_resp_valid;
    reg  [DATA_WIDTH-1:0] mem_resp_data;

    // -------------------------------------------------------------------------
    // Device Under Test (DUT)
    // -------------------------------------------------------------------------
    lfu_cache_controller #(
        .ADDR_WIDTH(ADDR_WIDTH),
        .DATA_WIDTH(DATA_WIDTH),
        .CACHE_DEPTH(CACHE_DEPTH),
        .FREQ_WIDTH(FREQ_WIDTH)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .req_valid(req_valid),
        .req_addr(req_addr),
        .req_ready(req_ready),
        .resp_valid(resp_valid),
        .resp_data(resp_data),
        .mem_req_valid(mem_req_valid),
        .mem_req_addr(mem_req_addr),
        .mem_req_ready(mem_req_ready),
        .mem_resp_valid(mem_resp_valid),
        .mem_resp_data(mem_resp_data)
    );

    // -------------------------------------------------------------------------
    // Clock Generation (Runs in parallel)
    // -------------------------------------------------------------------------
    initial begin
        clk = 0;
        forever #(CLK_PERIOD/2) clk = ~clk;
    end

    // -------------------------------------------------------------------------
    // Simulated Main Memory (HBM) Task
    // -------------------------------------------------------------------------
    // This block automatically responds to memory fetch requests from the DUT
    always @(posedge clk) begin
        if (mem_req_valid && mem_req_ready) begin
            mem_req_ready <= 1'b0; // Drop ready once accepted
            
            // Simulate memory latency (e.g., 5 clock cycles)
            repeat(5) @(posedge clk);
            
            // Return dummy data based on the requested address
            mem_resp_valid <= 1'b1;
            mem_resp_data  <= { {(DATA_WIDTH-32){1'b0}}, mem_req_addr }; // Pad address to data width
            
            @(posedge clk);
            mem_resp_valid <= 1'b0;
            mem_req_ready  <= 1'b1; // Ready for next request
        end
    end

    // Task to send a request from the Compute Unit
    task send_request(input [ADDR_WIDTH-1:0] addr);
        begin
            wait(req_ready);
            @(posedge clk);
            req_valid <= 1'b1;
            req_addr  <= addr;
            
            @(posedge clk);
            req_valid <= 1'b0;
            
            // Wait for response
            wait(resp_valid);
            $display("[%0t] Vector Received for Addr: %0h | Data: %0h", $time, addr, resp_data[31:0]);
            @(posedge clk);
        end
    endtask

    // -------------------------------------------------------------------------
    // Main Stimulus Block
    // -------------------------------------------------------------------------
    initial begin
        $dumpfile("lfu_cache_waves.vcd"); 
        $dumpvars(0, tb_lfu_cache);       
        
        // Explicitly force Icarus Verilog to dump the 2D arrays
        for (int k = 0; k < 16; k++) begin
            $dumpvars(0, dut.freq_count[k]);
            $dumpvars(0, dut.valid_bits[k]);
        end

        // Initialize Signals
        rst_n = 0;
        req_valid = 0;
        req_addr = 0;
        mem_req_ready = 1;
        mem_resp_valid = 0;
        mem_resp_data = 0;

        // Apply Reset
        #(CLK_PERIOD * 5);
        rst_n = 1;
        #(CLK_PERIOD * 2);
        
        $display("--- Starting LFU Cache Simulation ---");

        // PHASE 1: Fill the cache (16 unique addresses to fill CACHE_DEPTH)
        $display("\n--- PHASE 1: Cold Misses (Filling Cache) ---");
        for (int i = 0; i < 16; i++) begin
            send_request(i * 32); // Addresses: 0, 32, 64, 96...
        end

        // PHASE 2: Build Frequency (Make some vectors "Hot")
        $display("\n--- PHASE 2: LFU Frequency Building ---");
        // Hit Address 0 five times
        repeat(5) send_request(0);
        // Hit Address 32 three times
        repeat(3) send_request(32);
        // Hit Address 64 ten times (Hottest item)
        repeat(10) send_request(64);
        
        /* At this point:
           Addr 0: Freq = 6
           Addr 32: Freq = 4
           Addr 64: Freq = 11
           All other initial addresses: Freq = 1
        */

        // PHASE 3: Force an Eviction
        $display("\n--- PHASE 3: Forcing LFU Eviction ---");
        // Address 999 is not in the cache. The cache is full.
        // The LFU logic should evict one of the vectors with Freq = 1 (e.g., Addr 96)
        // It should NOT evict 0, 32, or 64.
        send_request(999);

        // Verify the Hot items are still there (these should be fast Hits, no memory delay)
        $display("\n--- PHASE 4: Verifying Hot Items Survived ---");
        send_request(64);
        send_request(0);

        #(CLK_PERIOD * 20);
        $display("--- Simulation Complete ---");
        $finish;
    end

endmodule