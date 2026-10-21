// Program Counter
// Holds the address of the instruction currently being executed and updates
// it once per cycle: pc+4 normally, or `target` when `src` is asserted
// (taken branch / jal / jalr).
module PC (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        src,
    input  logic [31:0] target,
    output logic [31:0] pc
);
    logic [31:0] pc_next;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            pc <= 32'b0;
        end else begin
            pc <= pc_next;
        end
    end

    always_comb begin
        pc_next = src ? target : (pc + 32'd4);
    end

endmodule
