// RV32I test program for tb_cpu
// Only the instruction subset this CPU targets:
//   ADD, ADDI, LUI, LW, SW, BNE, BLT, BGE, JAL, JALR
//
// The testbench (tb_cpu.sv) knows the expected register values for this
// program; keep them in sync if you edit it.

_start:
        addi    x5,  x0, 10         // x5  = 10
        addi    x6,  x0, 20         // x6  = 20
        add     x7,  x5, x6         // x7  = 30
        addi    x8,  x0, -1         // x8  = 0xFFFFFFFF   (imm sign extension)
        addi    x9,  x0, -5         // x9  = 0xFFFFFFFB
        add     x10, x9, x5         // x10 = 5
        lui     x11, 0x12345        // x11 = 0x12345000   (U-type immediate)

        // ---- load/store, negative offset included ----
        sw      x7,  64(x0)         // mem[64] = 30
        sw      x8,  68(x0)         // mem[68] = -1
        lw      x12, 64(x0)         // x12 = 30
        lw      x13, 68(x0)         // x13 = 0xFFFFFFFF

        // ---- BNE ----
        bne     x5,  x6, L_bne_ok   // taken   (10 != 20)
        addi    x14, x0, 111        // skipped
L_bne_ok:
        bne     x5,  x5, L_bne_nt   // not taken
        addi    x14, x0, 222        // x14 = 222
L_bne_nt:

        // ---- BLT (signed!) ----
        blt     x9,  x5, L_blt_ok   // -5 < 10 -> taken
        addi    x15, x0, 111        // skipped
L_blt_ok:
        blt     x5,  x9, L_blt_nt   // 10 < -5 -> not taken
        addi    x15, x0, 333        // x15 = 333
L_blt_nt:

        // ---- BGE (signed!) ----
        bge     x5,  x9, L_bge_ok   // 10 >= -5 -> taken
        addi    x16, x0, 111        // skipped
L_bge_ok:
        bge     x9,  x5, L_bge_nt   // -5 >= 10 -> not taken
        addi    x16, x0, 444        // x16 = 444
L_bge_nt:

        // ---- backward branch: 10 + 9 + ... + 1 ----
        addi    x20, x0, 0          // x20 = running sum
        addi    x21, x0, 10         // x21 = counter
sum_loop:
        add     x20, x20, x21
        addi    x21, x21, -1
        bne     x21, x0, sum_loop   // backward B-type offset
        // x20 = 55, x21 = 0

        // ---- JAL / JALR ----
        jal     x17, sub1           // x17 = return address (next instr)
        addi    x18, x0, 555        // x18 = 555, runs after the return
        jal     x0,  done           // unconditional jump, rd = x0

sub1:
        addi    x19, x0, 999        // x19 = 999
        jalr    x0,  0(x17)         // return to x17, rd = x0

done:
        jal     x0,  done           // park here forever

// ---- pass criteria (the testbench compares all 32 registers) ----
// expect x5  = 10
// expect x6  = 20
// expect x7  = 30
// expect x8  = 0xFFFFFFFF     ; addi x8,x0,-1  -> forces I-imm sign extension
// expect x9  = 0xFFFFFFFB     ; addi x9,x0,-5
// expect x10 = 5              ; -5 + 10
// expect x11 = 0x12345000     ; lui
// expect x12 = 30             ; lw read-back of the store
// expect x13 = 0xFFFFFFFF     ; lw read-back of the store
// expect x14 = 222            ; BNE taken / not taken
// expect x15 = 333            ; BLT signed
// expect x16 = 444            ; BGE signed
// expect x17 = 0x74           ; jal x17,sub1 -> link = 0x70+4
// expect x18 = 555            ; runs after jalr returns
// expect x19 = 999            ; inside sub1
// expect x20 = 55             ; backward-branch sum loop
// expect x21 = 0              ; loop counter after exit
