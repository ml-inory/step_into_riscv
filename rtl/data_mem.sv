// 1R1W 256x32bit Data Memory (1 KiB), word addressed.
//
// The read is asynchronous and the write is clocked, which is what a
// single-cycle load/store path needs.  (The previous version updated RD in
// the same always_ff as the write and only when NOT writing, so RD held
// stale data across a store and was one cycle late for a load.)
module DataMem (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [31:0] A,      // byte address
    input  logic        WE,
    input  logic [31:0] WD,
    output logic [31:0] RD
);
    logic [31:0] reg_array [0:255];

    // word index: 256 words = 1024 bytes
    logic [7:0] addr;

    assign addr = A[9:2];
    assign RD   = reg_array[addr];

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            for (int i = 0; i < 256; i = i + 1) begin
                reg_array[i] <= 32'b0;
            end
        end else if (WE) begin
            reg_array[addr] <= WD;
        end
    end

endmodule
