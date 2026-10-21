// 2R1W 32x32bit Register File
//
// x0 reads as zero and ignores writes (RISC-V hardwired zero).
//
// The two read ports are asynchronous: a single-cycle CPU needs RD1/RD2 in
// the same cycle the address is presented.  Only the write is clocked, and
// it is written on the rising edge so that a value produced this cycle is
// visible from the next cycle onward.
module RegFile (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [4:0]  A1,
    input  logic [4:0]  A2,
    input  logic [4:0]  A3,
    input  logic        WE3,
    input  logic [31:0] WD3,
    output logic [31:0] RD1,
    output logic [31:0] RD2
);
    logic [31:0] reg_array [0:31];

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            for (int i = 0; i < 32; i = i + 1) begin
                reg_array[i] <= 32'b0;
            end
        end else if (WE3 && (A3 != 5'd0)) begin
            reg_array[A3] <= WD3;
        end
    end

    assign RD1 = (A1 == 5'd0) ? 32'b0 : reg_array[A1];
    assign RD2 = (A2 == 5'd0) ? 32'b0 : reg_array[A2];

endmodule
