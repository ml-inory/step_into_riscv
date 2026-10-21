// 支持的指令:
// ADDI
// ADD
// BNE/BLT/BGE
// JAL/JALR
// LUI
// SW/LW
module ALU (
    input logic [6:0] op,
    input logic [2:0] funct3,
    input logic [6:0] funct7,
    input logic [31:0] A,
    input logic [31:0] B,
    output logic [31:0] result,
    output logic neq,
    output logic ge,
    output logic lt
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

    function bit is_jal (input [6:0] op, input [2:0] funct3, input [6:0] funct7);
        return (op_is_J(op) && funct3 == 3'b001);
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


    // 核心计算逻辑
    logic [31:0] sub_result;

    always_comb begin
        sub_result = A - B;

        if (is_add(op, funct3, funct7) || 
            is_addi(op, funct3, funct7) || 
            is_lw(op, funct3, funct7) ||
            is_sw(op, funct3, funct7)) begin
            result = A + B;
        end

        neq = (sub_result != 0);
        ge = (sub_result >= 0);
        lt = (sub_result < 0);
    end

endmodule