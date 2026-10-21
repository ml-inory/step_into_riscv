// Instruction ROM - 4 KiB, byte addressed, little-endian.
//
// The read is asynchronous: in a single-cycle CPU the instruction must be
// available in the same cycle the PC presents its address.  A registered
// read would add a cycle of latency and put the PC and the instruction out
// of step.
module InstrMem (
    input  logic        clk,     // unused, kept for interface symmetry
    input  logic        rst_n,   // unused
    input  logic [31:0] addr,
    output logic [31:0] instr
);
    logic [7:0] mem [0:4095];

    // word-aligned byte address; 12 bits so that a+3 cannot overflow
    logic [11:0] a;

    initial begin
        $readmemh("instr_mem.hex", mem);
    end

    assign a     = {addr[11:2], 2'b00};
    assign instr = { mem[a + 12'd3],
                     mem[a + 12'd2],
                     mem[a + 12'd1],
                     mem[a] };

endmodule
