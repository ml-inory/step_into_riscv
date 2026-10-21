// Main control unit - pure combinational decode.
//
// Takes the instruction fields plus the ALU condition flags (so the branch
// decision is made in the same cycle) and produces every control signal.
//
//   ResultSrc : 00 = ALUResult, 01 = data memory, 10 = pc+4 (for jal/jalr)
//   ImmSrc    : 0 = I, 1 = S, 2 = B, 3 = J, 4 = U
module CtrlUnit (
    input  logic [6:0] op,
    input  logic [2:0] funct3,
    input  logic [6:0] funct7,
    input  logic       neq,          // rs1 != rs2
    input  logic       ge,           // rs1 >= rs2, signed
    input  logic       lt,           // rs1 <  rs2, signed
    output logic       PCSrc,
    output logic [1:0] ResultSrc,
    output logic       MemWrite,
    output logic       ALUSrc,
    output logic [2:0] ImmSrc,
    output logic       RegWrite
);
    function bit op_is_R (input [6:0] op); return (op == 7'b0110011); endfunction
    function bit op_is_I (input [6:0] op); return (op == 7'b0010011); endfunction
    function bit op_is_B (input [6:0] op); return (op == 7'b1100011); endfunction
    function bit op_is_J (input [6:0] op); return (op == 7'b1101111); endfunction
    function bit op_is_S (input [6:0] op); return (op == 7'b0100011); endfunction

    // 指令判定
    function bit is_add (input [6:0] op, input [2:0] funct3, input [6:0] funct7);
        return (op_is_R(op) && funct3 == 3'b000 && funct7 == 7'b0000000);
    endfunction

    function bit is_addi (input [6:0] op, input [2:0] funct3, input [6:0] funct7);
        return (op_is_I(op) && funct3 == 3'b000);
    endfunction

    function bit is_bne (input [6:0] op, input [2:0] funct3, input [6:0] funct7);
        return (op_is_B(op) && funct3 == 3'b001);
    endfunction

    function bit is_blt (input [6:0] op, input [2:0] funct3, input [6:0] funct7);
        return (op_is_B(op) && funct3 == 3'b100);
    endfunction

    function bit is_bge (input [6:0] op, input [2:0] funct3, input [6:0] funct7);
        return (op_is_B(op) && funct3 == 3'b101);
    endfunction

    // J-type: funct3 is part of the immediate, not an opcode field.
    function bit is_jal (input [6:0] op, input [2:0] funct3, input [6:0] funct7);
        return op_is_J(op);
    endfunction

    function bit is_jalr (input [6:0] op, input [2:0] funct3, input [6:0] funct7);
        return (op == 7'b1100111 && funct3 == 3'b000);
    endfunction

    function bit is_lui (input [6:0] op, input [2:0] funct3, input [6:0] funct7);
        return (op == 7'b0110111);
    endfunction

    function bit is_lw (input [6:0] op, input [2:0] funct3, input [6:0] funct7);
        return (op == 7'b0000011 && funct3 == 3'b010);
    endfunction

    function bit is_sw (input [6:0] op, input [2:0] funct3, input [6:0] funct7);
        return (op == 7'b0100011 && funct3 == 3'b010);
    endfunction

    always_comb begin
        // Anything not recognised behaves as a NOP.
        PCSrc     = 1'b0;
        ResultSrc = 2'b00;
        MemWrite  = 1'b0;
        ALUSrc    = 1'b0;
        ImmSrc    = 3'd0;
        RegWrite  = 1'b0;

        if (is_add(op, funct3, funct7)) begin
            RegWrite = 1'b1;

        end else if (is_addi(op, funct3, funct7)) begin
            ALUSrc   = 1'b1;
            RegWrite = 1'b1;

        end else if (is_lui(op, funct3, funct7)) begin
            ALUSrc   = 1'b1;
            ImmSrc   = 3'd4;
            RegWrite = 1'b1;

        end else if (is_lw(op, funct3, funct7)) begin
            ALUSrc    = 1'b1;
            ResultSrc = 2'b01;       // write back from memory
            RegWrite  = 1'b1;

        end else if (is_sw(op, funct3, funct7)) begin
            ALUSrc   = 1'b1;
            ImmSrc   = 3'd1;         // S-type
            MemWrite = 1'b1;

        end else if (is_jal(op, funct3, funct7)) begin
            ImmSrc    = 3'd3;        // J-type
            ResultSrc = 2'b10;       // link = pc+4
            RegWrite  = 1'b1;
            PCSrc     = 1'b1;

        end else if (is_jalr(op, funct3, funct7)) begin
            ALUSrc    = 1'b1;        // target = rs1 + imm
            ResultSrc = 2'b10;       // link = pc+4
            RegWrite  = 1'b1;
            PCSrc     = 1'b1;

        end else if (is_bne(op, funct3, funct7)) begin
            ImmSrc = 3'd2;           // B-type
            PCSrc  = neq;

        end else if (is_blt(op, funct3, funct7)) begin
            ImmSrc = 3'd2;
            PCSrc  = lt;

        end else if (is_bge(op, funct3, funct7)) begin
            ImmSrc = 3'd2;
            PCSrc  = ge;
        end
    end

endmodule
