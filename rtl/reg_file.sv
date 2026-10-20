// 2R1W 32x32bit Register File
module RegFile (
    input logic clk,
    input logic rst_n,
    input logic [4:0] A1,
    input logic [4:0] A2,
    input logic [4:0] A3,
    input logic WE3,
    input logic [31:0] WD3,
    output logic [31:0] RD1,
    output logic [31:0] RD2
);
    reg [31:0] reg_array [0:31];

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            for (int i = 0; i < 32; i=i+1) begin
                reg_array[i] = 32'b0;
            end
        end else begin
            // write
            if (WE3) begin
                reg_array[A3] <= WD3;
            end

            RD1 <= reg_array[A1];
            RD2 <= reg_array[A2];
        end
    end

endmodule