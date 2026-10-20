// 1R1W 256x32bit Data Memory
module DataMem (
    input logic clk,
    input logic rst_n,
    input logic [4:0] A,
    input logic WE,
    input logic [31:0] WD,
    output logic [31:0] RD
);
    reg [31:0] reg_array [0:255];

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            for (int i = 0; i < 256; i=i+1) begin
                reg_array[i] = 32'b0;
            end
        end else begin
            // write
            if (WE) begin
                reg_array[A] <= WD;
            end else begin
                RD <= reg_array[A];
            end
        end
    end

endmodule