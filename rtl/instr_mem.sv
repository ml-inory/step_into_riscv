module InstrMem (
    input logic clk,
    input logic rst_n,
    input logic [31:0] addr,
    output logic [31:0] instr
);
    logic [7:0] mem [0:4095];
    logic [7:0] start_addr;

    initial begin
        $readmemh("instr_mem.hex", mem);
    end

    always_comb begin
        start_addr = addr[11:0];
    end

    always_ff @( posedge clk ) begin
        if (!rst_n) begin
            instr <= 32'b0;
        end else begin
            instr <= {  mem[start_addr + 3], 
                        mem[start_addr + 2], 
                        mem[start_addr + 1], 
                        mem[start_addr + 0]
                    };
        end
    end
endmodule