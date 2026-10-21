#!/usr/bin/env python3
"""
ivl.py - a drop-in replacement for the `iverilog` driver.

Why this exists
---------------
The Icarus Verilog installation on this machine (C:\\iverilog) is intact, but
`iverilog.exe` invokes its own backend tools (`ivlpp`, `ivl`) through C
`system()`, which on Windows needs a working `cmd.exe`.  In this environment
`cmd.exe` is non-functional (every `cmd /c ...` returns exit code 1 with no
output), so `iverilog.exe` aborts silently with no diagnostics.

`ivlpp.exe`, `ivl.exe` and `vvp.exe` all work correctly when spawned
directly, so this script reproduces the driver flow with plain CreateProcess
calls and no shell:

    ivlpp  (preprocess all sources into one stream)
      |
    ivl    (parse + elaborate; the vvp.tgt target writes the netlist)
      |      selected with  -p-o=<file>
      |
    vvp    (simulate; needs `-m system -M<libdir>` to load system.vpi)

Usage
-----
    python sim/ivl.py build -o sim/out.vvp rtl/*.sv tb/tb_cpu.sv
    python sim/ivl.py run   sim/out.vvp
    python sim/ivl.py     # compile + run in one go, see build_and_run()

As a library:
    from ivl import compile_sources, run_vvp
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

IVERILOG_ROOT = os.environ.get("IVERILOG_ROOT", r"C:\iverilog")
_LIB = os.path.join(IVERILOG_ROOT, "lib", "ivl")
IVLPP = os.path.join(_LIB, "ivlpp.exe")
IVL = os.path.join(_LIB, "ivl.exe")
VVP = os.path.join(IVERILOG_ROOT, "bin", "vvp.exe")
VVP_CONF = os.path.join(_LIB, "vvp.conf")


class CompileError(RuntimeError):
    pass


def compile_sources(sources, out_vvp, generation="2012", defines=None,
                    incdirs=None, top=None, verbose=False):
    """Preprocess and elaborate `sources` into a vvp netlist at `out_vvp`."""
    sources = [os.path.abspath(s) for s in sources]
    missing = [s for s in sources if not os.path.isfile(s)]
    if missing:
        raise CompileError("source file(s) not found:\n  " +
                           "\n  ".join(missing))

    out_vvp = os.path.abspath(out_vvp)
    out_dir = os.path.dirname(out_vvp) or "."
    os.makedirs(out_dir, exist_ok=True)

    tmp = tempfile.mkdtemp(prefix="ivl_")
    try:
        # The preprocessor's -F file holds -D/-I style directives.
        pp_flags = os.path.join(tmp, "pp_flags.txt")
        with open(pp_flags, "w") as f:
            for d in (defines or []):
                f.write(f"-D{d}\n")
            for i in (incdirs or []):
                f.write(f"-I{i}\n")

        # 1) preprocess --------------------------------------------------
        # Each source is preprocessed on its own, exactly like the real
        # driver does.  Concatenating them into one stream would corrupt
        # the result whenever a file does not end with a newline (which is
        # the case for every file in this repo: "endmodule" would end up
        # glued to "module").
        pre_files = []
        for n, src in enumerate(sources):
            pre = os.path.join(tmp, f"unit{n}.pre")
            cmd = [IVLPP, f"-F{pp_flags}", f"-o{pre}", src]
            if verbose:
                print("[ivlpp]", " ".join(cmd), file=sys.stderr)
            rc = subprocess.run(cmd).returncode
            if rc != 0:
                raise CompileError(f"ivlpp failed on {src} (rc={rc})")
            if not os.path.isfile(pre) or os.path.getsize(pre) == 0:
                raise CompileError(f"ivlpp produced no output for {src}")
            pre_files.append(pre)

        # 2) elaborate ---------------------------------------------------
        # ivl reads its own config with `-C`; `generation:` is how the
        # -g<generation> switch is expressed.  `-p-o=` names the netlist.
        ivl_conf = os.path.join(tmp, "ivl.conf")
        with open(ivl_conf, "w") as f:
            f.write(f"generation:{generation}\n")
            if top:
                f.write(f"top:{top}\n")

        cmd = [IVL, f"-C{ivl_conf}", f"-C{VVP_CONF}",
               f"-p-o={out_vvp}"] + pre_files
        if verbose:
            print("[ivl]  ", " ".join(cmd), file=sys.stderr)
        rc = subprocess.run(cmd).returncode
        if rc != 0:
            raise CompileError(f"ivl failed with rc={rc}")
        if not os.path.isfile(out_vvp) or os.path.getsize(out_vvp) == 0:
            raise CompileError("elaboration produced no netlist")
        return out_vvp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_vvp(netlist, args=None, cwd=None, verbose=False):
    """Run a compiled netlist.  `-m system` is required because the netlist
    has no :vpi_module directive of its own.

    vvp's command line is `vvp [options] input-file [+plusargs...]`, so any
    +plusarg has to come *after* the netlist.
    """
    cmd = [VVP, "-m", "system", f"-M{_LIB}", netlist] + (args or [])
    if verbose:
        print("[vvp]  ", " ".join(cmd), file=sys.stderr)
    return subprocess.run(cmd, cwd=cwd).returncode


def build_and_run(sources, out_vvp, workdir=None, vvp_args=None,
                  verbose=False):
    compile_sources(sources, out_vvp, verbose=verbose)
    net = os.path.abspath(out_vvp)
    rc = run_vvp(net, vvp_args, cwd=workdir, verbose=verbose)
    if rc != 0:
        print(f"error: vvp exited with rc={rc}", file=sys.stderr)
    return rc


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    if argv[1] == "run":
        if len(argv) < 3:
            print("usage: ivl.py run <netlist.vvp> [vvp args]", file=sys.stderr)
            return 2
        return run_vvp(argv[2], argv[3:])

    if argv[1] != "build":
        print(f"unknown command: {argv[1]}", file=sys.stderr)
        return 2

    out, sources, defines, incdirs = "out.vvp", [], [], []
    gen = "2012"
    verbose = False
    i = 2
    while i < len(argv):
        a = argv[i]
        if a == "-o":
            i += 1
            out = argv[i]
        elif a.startswith("-o") and len(a) > 2:
            out = a[2:]
        elif a.startswith("-g") and len(a) > 2:
            gen = a[2:]
        elif a.startswith("-D") and len(a) > 2:
            defines.append(a[2:])
        elif a.startswith("-I") and len(a) > 2:
            incdirs.append(a[2:])
        elif a in ("-v", "--verbose"):
            verbose = True
        elif a.startswith("-"):
            print(f"warning: ignoring unsupported option {a}", file=sys.stderr)
        else:
            sources.append(a)
        i += 1

    if not sources:
        print("error: no source files", file=sys.stderr)
        return 2
    compile_sources(sources, out, gen, defines, incdirs, verbose=verbose)
    print(f"built {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
