//----------------------------------------------------------------------------
// Single-cycle RV32I CPU
//
// Supported instructions:
//   ADD  ADDI  LUI  LW  SW  BNE  BLT  BGE  JAL  JALR
//
// Dataflow for the instruction at `pc` (everything below is combinational
// except the PC, the register file write and the data memory write):
//
//   pc --> InstrMem --> instr --> CtrlUnit --> control signals
//                              --> RegFile  --> srcA / RD2
//                              --> ALU      --> ALUResult --> DataMem (lw/sw)
//   next pc = pc+4 | pc+ImmExt (branch/jal) | rs1+ImmExt (jalr)
//   write back: ALUResult | mem read data | pc+4
//----------------------------------------------------------------------------
module CPU (
    input logic clk,
    input logic rst_n
);
    // ---------------- instruction fields ----------------
    logic [6:0] op;
    logic [2:0] funct3;
    logic [6:0] funct7;
    logic [4:0] rs1, rs2, rd;

    // ---------------- control ----------------
    logic       PCSrc, MemWrite, ALUSrc, RegWrite;
    logic [1:0] ResultSrc;
    logic [2:0] ImmSrc;

    // ---------------- datapath ----------------
    logic [31:0] pc, pc_plus4, PCTarget;
    logic [31:0] instr, ImmExt;
    logic [31:0] srcA, srcB, RD2;
    logic [31:0] ALUResult, ReadData, wb_data;
    logic        neq, ge, lt;
    logic        is_jalr;

    assign op     = instr[6:0];
    assign funct3 = instr[14:12];
    assign funct7 = instr[31:25];
    assign rs1    = instr[19:15];
    assign rs2    = instr[24:20];
    assign rd     = instr[11:7];

    assign pc_plus4 = pc + 32'd4;
    assign is_jalr  = (op == 7'b1100111);

    // ALU operand B: register or immediate
    assign srcB = ALUSrc ? ImmExt : RD2;

    // jalr jumps to rs1+imm (ALU result); everything else is pc relative
    assign PCTarget = is_jalr ? {ALUResult[31:1], 1'b0} : (pc + ImmExt);

    // ---------------- immediate generation ----------------
    // Each form is sign extended to exactly 32 bits.  Concatenating a wider
    // field than needed and letting the assignment truncate it silently
    // drops the top bits, i.e. it turns a negative immediate into a small
    // positive one.
    logic [31:0] imm_i, imm_s, imm_b, imm_j, imm_u;

    assign imm_i = {{20{instr[31]}}, instr[31:20]};
    assign imm_s = {{20{instr[31]}}, instr[31:25], instr[11:7]};
    assign imm_b = {{19{instr[31]}}, instr[31], instr[7],
                    instr[30:25], instr[11:8], 1'b0};
    assign imm_j = {{11{instr[31]}}, instr[31], instr[19:12],
                    instr[20], instr[30:21], 1'b0};
    assign imm_u = {instr[31:12], 12'b0};

    assign ImmExt = (ImmSrc == 3'd0) ? imm_i :   // I
                    (ImmSrc == 3'd1) ? imm_s :   // S
                    (ImmSrc == 3'd2) ? imm_b :   // B
                    (ImmSrc == 3'd3) ? imm_j :   // J
                                       imm_u;    // 3'd4, U-type

    // ---------------- write-back mux ----------------
    assign wb_data = (ResultSrc == 2'b01) ? ReadData :   // load
                     (ResultSrc == 2'b10) ? pc_plus4 :   // jal / jalr link
                                            ALUResult;   // ALU / lui

    // ---------------- submodules ----------------
    PC u_pc (
        .clk    (clk),
        .rst_n  (rst_n),
        .src    (PCSrc),
        .target (PCTarget),
        .pc     (pc)
    );

    InstrMem u_instr_mem (
        .clk   (clk),
        .rst_n (rst_n),
        .addr  (pc),
        .instr (instr)
    );

    CtrlUnit u_ctrl_unit (
        .op        (op),
        .funct3    (funct3),
        .funct7    (funct7),
        .neq       (neq),
        .ge        (ge),
        .lt        (lt),
        .PCSrc     (PCSrc),
        .ResultSrc (ResultSrc),
        .MemWrite  (MemWrite),
        .ALUSrc    (ALUSrc),
        .ImmSrc    (ImmSrc),
        .RegWrite  (RegWrite)
    );

    RegFile u_reg_file (
        .clk   (clk),
        .rst_n (rst_n),
        .A1    (rs1),
        .A2    (rs2),
        .A3    (rd),
        .WE3   (RegWrite),
        .WD3   (wb_data),
        .RD1   (srcA),
        .RD2   (RD2)
    );

    ALU u_alu (
        .op      (op),
        .funct3  (funct3),
        .funct7  (funct7),
        .A       (srcA),
        .B       (srcB),
        .result  (ALUResult),
        .neq     (neq),
        .ge      (ge),
        .lt      (lt)
    );

    DataMem u_data_mem (
        .clk   (clk),
        .rst_n (rst_n),
        .A     (ALUResult),
        .WE    (MemWrite),
        .WD    (RD2),
        .RD    (ReadData)
    );

endmodule
