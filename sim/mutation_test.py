#!/usr/bin/env python3
"""
mutation_test.py - prove that tb_cpu actually detects the bugs it claims to.

For every entry below it copies rtl/ to a scratch directory, re-introduces
one specific bug, rebuilds and runs the testbench, and checks that the run
FAILS.  When a bug is not caught (or the wrong ones are) it is reported.

    python sim/mutation_test.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (name, file, old, new, expected failing checks mentioned in the log)
MUTANTS = [
    (
        "unsigned BLT/BGE comparison",
        "alu.sv",
        "ge  = ($signed(A) >= $signed(B));\n        lt  = ($signed(A) <  $signed(B));",
        "ge  = (A >= B);\n        lt  = (A < B);",
        ["x15", "x16"],
    ),
    (
        "zero-extended I immediate",
        "cpu.sv",
        "assign imm_i = {{20{instr[31]}}, instr[31:20]};",
        "assign imm_i = {20'b0, instr[31:20]};",
        ["x8", "x9"],
    ),
    (
        "store address built from rs2 (ALUSrc=0 for SW)",
        "ctrl_unit.sv",
        "            ALUSrc   = 1'b1;\n            ImmSrc   = 3'd1;         // S-type",
        "            ImmSrc   = 3'd1;         // S-type",
        ["x12"],
    ),
    (
        "LUI uses the I-type immediate",
        "cpu.sv",
        "assign imm_u = {instr[31:12], 12'b0};",
        "assign imm_u = {{20{instr[31]}}, instr[31:20]};",
        ["x11"],
    ),
    (
        "jal/jalr link value is ALUResult instead of pc+4",
        "cpu.sv",
        "(ResultSrc == 2'b10) ? pc_plus4 :   // jal / jalr link",
        "(ResultSrc == 2'b10) ? ALUResult : // jal / jalr link",
        ["x17"],
    ),
    (
        "x0 not hardwired (writes to x0 take effect)",
        "reg_file.sv",
        "else if (WE3 && (A3 != 5'd0)) begin",
        "else if (WE3) begin",
        ["x0 "],
    ),
    (
        "is_jal() requires funct3==001",
        "ctrl_unit.sv",
        "    function bit is_jal (input [6:0] op, input [2:0] funct3, input [6:0] funct7);\n        return op_is_J(op);",
        "    function bit is_jal (input [6:0] op, input [2:0] funct3, input [6:0] funct7);\n        return (op_is_J(op) && funct3 == 3'b001);",
        ["never parked"],
    ),
    (
        "registered register-file read (1-cycle latency)",
        "reg_file.sv",
        "    assign RD1 = (A1 == 5'd0) ? 32'b0 : reg_array[A1];\n"
        "    assign RD2 = (A2 == 5'd0) ? 32'b0 : reg_array[A2];",
        "    always_ff @(posedge clk) begin\n"
        "        RD1 <= (A1 == 5'd0) ? 32'b0 : reg_array[A1];\n"
        "        RD2 <= (A2 == 5'd0) ? 32'b0 : reg_array[A2];\n"
        "    end",
        ["x5"],
    ),
]


def run(rtl_dir):
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "run_tb.py"), "--rtl", rtl_dir],
        capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    src = os.path.join(ROOT, "rtl")
    failures = 0

    print("=" * 72)
    print(" baseline: unmodified rtl/ must PASS")
    print("=" * 72)
    rc, log = run(src)
    if rc == 0 and "RESULT: PASS" in log:
        print("  ok   baseline passes")
    else:
        failures += 1
        print("  BAD  baseline does not pass (rc=%d)" % rc)

    for name, fname, old, new, expect in MUTANTS:
        tmp = tempfile.mkdtemp(prefix="mut_")
        try:
            for f in os.listdir(src):
                if f.endswith(".sv"):
                    shutil.copy(os.path.join(src, f), tmp)
            path = os.path.join(tmp, fname)
            with open(path) as f:
                text = f.read()
            if old not in text:
                print(f"  SKIP {name}: pattern not found in {fname}")
                failures += 1
                continue
            with open(path, "w") as f:
                f.write(text.replace(old, new, 1))

            rc, log = run(tmp)
            caught = rc != 0 and "RESULT: FAIL" in log
            missing = [e for e in expect if e not in log]

            status = "ok  " if caught else "MISS"
            if not caught:
                failures += 1
            print(f"  {status} {name}")
            if caught:
                nfail = log.count("  FAIL  x")
                print(f"         -> FAIL as expected, "
                      f"{nfail} register mismatch(es)"
                      + (f", missing markers {missing}" if missing else ""))
            else:
                print("         -> BUG NOT DETECTED, this test is too weak")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("=" * 72)
    if failures == 0:
        print(" all mutants were detected by tb_cpu")
    else:
        print(f" {failures} problem(s) - the testbench needs strengthening")
    print("=" * 72)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
