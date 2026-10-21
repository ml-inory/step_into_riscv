#!/usr/bin/env python3
"""
run_tb.py - assemble a test program, build the testbench and run it.

    python sim/run_tb.py                      # the full regression program
    python sim/run_tb.py --program sum        # 1 + 2 + ... + 10
    python sim/run_tb.py --program tb/program_sum.S
    python sim/run_tb.py --all                # every tb/program*.S
    python sim/run_tb.py --trace              # per-cycle pc / instruction

`--program` accepts a path, or a short name: `sum` is looked up as
tb/sum.S, tb/sum, tb/program_sum.S or tb/program_sum.

The RTL is compiled once; each program then only swaps instr_mem.hex and
expected.hex, because the program is loaded by $readmemh at simulation
start rather than being baked into the netlist.

Everything lands in sim/build/.
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import ivl  # noqa: E402  (local module)


def resolve_program(arg, tb_dir):
    """Accept a path or a short name like 'sum'."""
    if arg is None:
        return os.path.join(tb_dir, "program.S")
    if os.path.isfile(arg):
        return os.path.abspath(arg)
    for cand in (arg, arg + ".S", f"program_{arg}.S", f"program_{arg}"):
        path = os.path.join(tb_dir, cand)
        if os.path.isfile(path):
            return path
    return os.path.abspath(arg)      # let the assembler report it


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rtl", default=os.path.join(ROOT, "rtl"))
    ap.add_argument("--tb", default=os.path.join(ROOT, "tb"))
    ap.add_argument("--build", default=os.path.join(HERE, "build"))
    ap.add_argument("--program", default=None,
                    help="assembly source or short name (default program.S)")
    ap.add_argument("--all", action="store_true",
                    help="run every tb/program*.S")
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--sim-args", default="", help="extra vvp arguments")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-build", action="store_true",
                    help="reuse an existing netlist")
    args = ap.parse_args(argv)

    build = os.path.abspath(args.build)
    os.makedirs(build, exist_ok=True)

    asm = os.path.join(args.tb, "asm.py")
    tb_file = os.path.join(args.tb, "tb_cpu.sv")
    netlist = os.path.join(build, "tb_cpu.vvp")

    # ---- which programs? ------------------------------------------------
    if args.all:
        programs = sorted(glob.glob(os.path.join(args.tb, "program*.S")))
        if not programs:
            print(f"error: no program*.S in {args.tb}", file=sys.stderr)
            return 1
    else:
        programs = [resolve_program(args.program, args.tb)]

    # ---- elaborate once ------------------------------------------------
    if not args.no_build:
        rtl = sorted(os.path.join(args.rtl, f)
                     for f in os.listdir(args.rtl) if f.endswith(".sv"))
        if not rtl:
            print(f"error: no .sv sources in {args.rtl}", file=sys.stderr)
            return 1
        try:
            ivl.compile_sources(rtl + [tb_file], netlist, verbose=args.verbose)
        except ivl.CompileError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1

    # ---- assemble + simulate each program ------------------------------
    results = []
    for prog in programs:
        print("")
        print("=" * 68)
        print(f" {os.path.relpath(prog, ROOT)}")
        print("=" * 68)

        r = subprocess.run([sys.executable, asm, prog, "-o", build])
        if r.returncode != 0:
            print("error: assembly failed", file=sys.stderr)
            results.append((prog, r.returncode))
            continue

        vvp_args = (["+trace"] if args.trace else []) + args.sim_args.split()
        # instr_mem.hex / expected.hex are opened relative to the cwd
        rc = ivl.run_vvp(netlist, vvp_args, cwd=build, verbose=args.verbose)
        results.append((prog, rc))

    # ---- summary -------------------------------------------------------
    if len(results) > 1:
        print("")
        print("=" * 68)
        print(" summary")
        print("=" * 68)
        for prog, rc in results:
            print(f"  {'PASS' if rc == 0 else 'FAIL'}  "
                  f"{os.path.relpath(prog, ROOT)}")

    return 0 if all(rc == 0 for _, rc in results) else 1


if __name__ == "__main__":
    sys.exit(main())
