#!/usr/bin/env python3
"""
Tiny RV32I assembler for the test program.

Supports exactly the instruction subset the CPU in rtl/ targets:
    add  addi  lui  lw  sw  bne  blt  bge  jal  jalr

It emits:
    <out>/instr_mem.hex   4096 lines of one byte each, little-endian, the
                          filename InstrMem's own $readmemh() expects.
    <out>/expected.hex    32 words: the final register state the testbench
                          must see, built from the program's directives.
    <out>/program.lst     human-readable address + bytes + source listing.

Pass criteria live in the program itself, so every program carries its own
oracle:

    // expect x1 = 55
    // expect x2 = 0x1f
    // expect x3 = 10   ; free-form note after the value

Registers without a directive are expected to be 0.

Usage:
    python tb/asm.py tb/program.S -o sim/build
    python tb/asm.py tb/program.S -o sim/build --dump-syms
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# opcode / funct3 / funct7 for the supported subset
ALU_R = {"add": (0b0110011, 0b000, 0b0000000)}
ALU_I = {"addi": (0b0010011, 0b000)}
LOADS = {"lw": (0b0000011, 0b010)}
STORES = {"sw": (0b0100011, 0b010)}
BRANCHES = {"bne": (0b1100011, 0b001),
            "blt": (0b1100011, 0b100),
            "bge": (0b1100011, 0b101)}
JUMPS = {"jal": 0b1101111}
JALR = 0b1100111
LUI = 0b0110111


def _reg(tok: str) -> int:
    t = tok.strip().lower()
    if not t.startswith("x"):
        raise SyntaxError(f"bad register '{tok}'")
    n = int(t[1:])
    if not 0 <= n <= 31:
        raise SyntaxError(f"register out of range: {tok}")
    return n


def _imm(tok: str) -> int:
    t = tok.strip().replace("_", "")
    return int(t, 0)


def _check_range(v, bits, what):
    lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    if not lo <= v <= hi:
        raise SyntaxError(f"{what} immediate {v} does not fit in {bits} bits")
    return v & ((1 << bits) - 1)


def enc_r(f7, rs2, rs1, f3, rd, op):
    return (f7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def enc_i(imm, rs1, f3, rd, op):
    u = _check_range(imm, 12, "I-type")
    return (u << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def enc_s(imm, rs2, rs1, f3, op):
    u = _check_range(imm, 12, "S-type")
    return (((u >> 5) & 0x7F) << 25) | (rs2 << 20) | (rs1 << 15) | \
           (f3 << 12) | ((u & 0x1F) << 7) | op


def enc_b(imm, rs2, rs1, f3, op):
    if imm & 1:
        raise SyntaxError("branch offset must be even")
    u = _check_range(imm, 13, "B-type")
    return (((u >> 12) & 1) << 31) | (((u >> 5) & 0x3F) << 25) | \
           (rs2 << 20) | (rs1 << 15) | (f3 << 12) | \
           (((u >> 1) & 0xF) << 8) | (((u >> 11) & 1) << 7) | op


def enc_u(imm, rd, op):
    u = imm & 0xFFFFF
    if imm < 0 or imm > 0xFFFFF:
        raise SyntaxError("U-type immediate must be 0..0xFFFFF")
    return (u << 12) | (rd << 7) | op


def enc_j(imm, rd, op):
    if imm & 1:
        raise SyntaxError("jal offset must be even")
    u = _check_range(imm, 21, "J-type")
    return (((u >> 20) & 1) << 31) | (((u >> 1) & 0x3FF) << 21) | \
           (((u >> 11) & 1) << 20) | (((u >> 12) & 0xFF) << 12) | \
           (rd << 7) | op


TOKEN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):")
MEMOP = re.compile(r"^(-?\w+)\s*\(\s*(x\d+)\s*\)$", re.I)
LABELOP = re.compile(r"^[A-Za-z_.][A-Za-z0-9_.]*$")

# Expected-result directive, so a program carries its own pass criteria:
#     // expect x1 = 55
#     # expect x2 = 0x1f
#     // expect x3 = 10   ; anything after a ';' is a note
# The testbench reads the generated expected.hex and compares the whole
# register file against it; registers with no directive must stay 0.
EXPECT = re.compile(
    r"^\s*(?://|#)\s*expect\s+x(\d+)\s*=\s*([^\s;]+)\s*(?:;.*)?$", re.I)


def parse(text):
    """-> (items, expects).

    items   : list of (line_no, kind, payload), kind in {'insn','label'}
    expects : {reg_index: 32-bit value}
    """
    items, expects = [], {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        m = EXPECT.match(raw)
        if m:
            reg = int(m.group(1))
            if not 0 <= reg <= 31:
                raise SyntaxError(f"line {lineno}: x{reg} is not a register")
            try:
                val = int(m.group(2).replace("_", ""), 0)
            except ValueError:
                raise SyntaxError(
                    f"line {lineno}: bad expect value '{m.group(2)}'")
            if reg == 0 and (val & 0xFFFFFFFF) != 0:
                raise SyntaxError(
                    f"line {lineno}: x0 is hardwired to zero, cannot expect "
                    f"0x{val & 0xFFFFFFFF:08X}")
            expects[reg] = val & 0xFFFFFFFF
            continue

        line = raw.split("//")[0].split("#")[0].rstrip()
        if not line.strip():
            continue
        while True:
            m = TOKEN.match(line.strip())
            if not m:
                break
            items.append((lineno, "label", m.group(1)))
            line = line.strip()[m.end():].strip()
            if not line:
                break
        if not line:
            continue
        items.append((lineno, "insn", line.split()))
    return items, expects


def assemble(text):
    items, expects = parse(text)

    # pass 1: label addresses
    syms, addr = {}, 0
    for lineno, kind, payload in items:
        if kind == "label":
            if payload in syms:
                raise SyntaxError(f"line {lineno}: duplicate label '{payload}'")
            syms[payload] = addr
        else:
            addr += 4

    # pass 2: encode
    words, listing = [], []
    addr = 0
    for lineno, kind, payload in items:
        if kind == "label":
            continue
        toks = payload
        op = toks[0].lower()
        args = [a.strip() for a in " ".join(toks[1:]).split(",") if a.strip()]
        pc = addr

        try:
            if op in ALU_R:
                o, f3, f7 = ALU_R[op]
                w = enc_r(f7, _reg(args[2]), _reg(args[1]), f3, _reg(args[0]), o)
            elif op in ALU_I:
                o, f3 = ALU_I[op]
                w = enc_i(_imm(args[2]), _reg(args[1]), f3, _reg(args[0]), o)
            elif op == "lui":
                w = enc_u(_imm(args[1]), _reg(args[0]), LUI)
            elif op in LOADS:
                o, f3 = LOADS[op]
                m = MEMOP.match(args[1])
                if not m:
                    raise SyntaxError(f"bad memory operand '{args[1]}'")
                w = enc_i(_imm(m.group(1)), _reg(m.group(2)), f3,
                          _reg(args[0]), o)
            elif op in STORES:
                o, f3 = STORES[op]
                m = MEMOP.match(args[1])
                if not m:
                    raise SyntaxError(f"bad memory operand '{args[1]}'")
                w = enc_s(_imm(m.group(1)), _reg(args[0]), _reg(m.group(2)),
                          f3, o)
            elif op in BRANCHES:
                o, f3 = BRANCHES[op]
                if args[2] not in syms:
                    raise SyntaxError(f"unknown label '{args[2]}'")
                w = enc_b(syms[args[2]] - pc, _reg(args[1]), _reg(args[0]),
                          f3, o)
            elif op == "jal":
                if args[1] not in syms:
                    raise SyntaxError(f"unknown label '{args[1]}'")
                w = enc_j(syms[args[1]] - pc, _reg(args[0]), JUMPS[op])
            elif op == "jalr":
                m = MEMOP.match(args[1])
                if not m:
                    raise SyntaxError(f"bad memory operand '{args[1]}'")
                w = enc_i(_imm(m.group(1)), _reg(m.group(2)), 0b000,
                          _reg(args[0]), JALR)
            else:
                raise SyntaxError(f"unsupported instruction '{op}'")
        except SyntaxError as e:
            raise SyntaxError(f"line {lineno}: {e}  [{op} {' '.join(args)}]")

        words.append(w & 0xFFFFFFFF)
        listing.append((pc, w & 0xFFFFFFFF, " ".join(toks)))
        addr += 4

    return syms, words, listing, expects


def emit(syms, words, listing, expects, outdir):
    os.makedirs(outdir, exist_ok=True)

    # 4096 bytes, little-endian, one hex byte per line
    mem = bytearray(4096)
    for i, w in enumerate(words):
        base = i * 4
        if base + 3 >= len(mem):
            raise SystemExit("program does not fit in 4096 bytes of instr mem")
        mem[base:base + 4] = w.to_bytes(4, "little")

    hexpath = os.path.join(outdir, "instr_mem.hex")
    with open(hexpath, "w") as f:
        for b in mem:
            f.write(f"{b:02x}\n")

    # 32 words: the register state the testbench must see at the end
    exppath = os.path.join(outdir, "expected.hex")
    with open(exppath, "w") as f:
        for r in range(32):
            f.write(f"{expects.get(r, 0):08x}\n")

    lstpath = os.path.join(outdir, "program.lst")
    with open(lstpath, "w") as f:
        f.write("addr     machine    source\n")
        for pc, w, src in listing:
            b = w.to_bytes(4, "little")
            f.write(f"{pc:04x}  {b[3]:02x}{b[2]:02x}{b[1]:02x}{b[0]:02x}"
                    f"   {src}\n")
        f.write("\nlabels:\n")
        for name, a in syms.items():
            f.write(f"  {name} = 0x{a:04x} ({a})\n")
        f.write("\nexpected final register state:\n")
        for r in range(32):
            if r in expects:
                f.write(f"  x{r:<2} = 0x{expects[r]:08x}\n")

    sympath = os.path.join(outdir, "symbols.json")
    with open(sympath, "w") as f:
        json.dump(syms, f, indent=2)

    return hexpath, lstpath, sympath


SELFTEST = [
    # (source, expected word) -- expected values cross-checked against
    # well-known RV32I encodings, e.g. addi x1,x0,-1 = 0xFFF00093,
    # beq x1,x2,+8 = 0x00208463, jal x1,+4 = 0x004000EF.
    ("addi x1, x0, -1", 0xFFF00093),
    ("addi x5, x0, 10", 0x00A00293),
    ("add x7, x5, x6", 0x006283B3),
    ("lui x11, 0x12345", 0x123455B7),
    ("sw x1, 0(x2)", 0x00112023),
    ("sw x7, 64(x0)", 0x04702023),
    ("lw x12, 64(x0)", 0x04002603),
    ("jalr x0, 0(x17)", 0x00088067),
    ("bne x5, x6, tgt", 0x00629263),
]


def selftest():
    ok = True
    for src, want in SELFTEST:
        # `tgt` sits right after the instruction under test, so the offset
        # for the branch case is +4.
        text = src + "\ntgt:\n  addi x5, x0, 0\n"
        _, words, _, _ = assemble(text)
        got = words[0]
        flag = "ok " if got == want else "BAD"
        if got != want:
            ok = False
        print(f"{flag} {src:24s} got 0x{got:08X} want 0x{want:08X}")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="assembly file")
    ap.add_argument("-o", "--outdir", default="sim/build")
    ap.add_argument("--dump-syms", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if not a.source:
        ap.error("no source file (or use --selftest)")

    with open(a.source) as f:
        text = f.read()
    try:
        syms, words, listing, expects = assemble(text)
    except SyntaxError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    hexpath, lstpath, sympath = emit(syms, words, listing, expects, a.outdir)
    print(f"assembled {len(words)} instructions -> {hexpath}")
    print(f"listing  -> {lstpath}")
    if expects:
        parts = ", ".join(f"x{r}=0x{v:08x}" for r, v in sorted(expects.items()))
        print(f"expected registers: {parts}")
    else:
        print("warning: no '// expect xN = value' directives; the testbench "
              "will require every register to be 0", file=sys.stderr)
    if a.dump_syms:
        for k, v in syms.items():
            print(f"  {k} = {v:#06x} ({v})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
