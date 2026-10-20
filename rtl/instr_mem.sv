module InstrMem (
    input logic clk,
    input logic rst_n,
    input logic [31:0] addr,
    output logic [31:0] instr
);
    logic [7:0] mem [0:255];

    initial begin
        $readmemh("instr_mem.hex", mem);
    end

    always_ff @( posedge clk ) begin
        if (!rst_n) begin
            instr <= 32'b0;
        end else begin
            instr <= mem[addr[9:2]];
        end
    end
endmodule