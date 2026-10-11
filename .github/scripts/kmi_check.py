#!/usr/bin/env python3
"""Compare exported-symbol CRCs of a built GKI kernel against the frozen KMI.

Vendor modules (e.g. Xiaomi houji's vendor_dlkm) are built against the CRCs in
android/abi_gki_aarch64.stg. If our patched kernel exports a symbol with a
different CRC, the module loader rejects the module ("disagrees about version
of symbol") and the device bootloops. Ported from GKID-Kernels' kmi-check-6.x.py
(author: Pzqqt), minus the `rich` dependency.

Exit codes: 0 = KMI intact, 1 = CRC mismatch, 2 = usage error.
"""

import sys


def parse_stg(path):
    """Return {symbol: crc} for every elf_symbol block that carries a crc."""
    symbols, block = {}, None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line == "elf_symbol {":
                block = {}
            elif line == "}" and block is not None:
                if "name" in block and "crc" in block:
                    symbols[block["name"]] = int(block["crc"], 16)
                block = None
            elif block is not None and ":" in line:
                key, value = (s.strip() for s in line.split(":", 1))
                block[key] = value.strip('"')
    return symbols


def parse_symvers(path):
    """vmlinux.symvers lines: <crc>\t<symbol>\t<module>\t<export type>[\t<ns>]."""
    symbols = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                symbols[parts[1]] = int(parts[0], 16)
    return symbols


def compare(stg, symvers):
    missing = sorted(stg.keys() - symvers.keys())
    mismatched = sorted(
        (name, stg[name], symvers[name])
        for name in stg.keys() & symvers.keys()
        if stg[name] != symvers[name]
    )
    return missing, mismatched


def main(argv):
    if len(argv) != 3:
        print(f"Usage: {argv[0]} <abi_gki_aarch64.stg> <vmlinux.symvers>")
        return 2
    stg, symvers = parse_stg(argv[1]), parse_symvers(argv[2])
    if not stg:
        print(f"No CRC-bearing elf_symbol entries in {argv[1]}; cannot verify KMI.")
        return 2

    missing, mismatched = compare(stg, symvers)
    # Missing symbols only break modules that use them; report, don't fail.
    if missing:
        print(f"Warning: {len(missing)} KMI symbol(s) not exported by this kernel:")
        for name in missing:
            print(f"  - {name}")
    if not mismatched:
        print(f"KMI OK: {len(stg)} symbols checked, no CRC mismatch.")
        return 0
    print(f"{'Symbol':<60} {'KMI (.stg)':<12} {'Built':<12}")
    for name, want, got in mismatched:
        print(f"{name:<60} 0x{want:08x}   0x{got:08x}")
    print(f"Found {len(mismatched)} symbol(s) with mismatched CRC - vendor modules will refuse to load.")
    return 1


def _self_check():
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        stg_path, sv_path = os.path.join(d, "a.stg"), os.path.join(d, "v.symvers")
        with open(stg_path, "w", encoding="utf-8") as f:
            f.write(
                'elf_symbol {\n  id: 0x1\n  name: "ok"\n  crc: 0x0000abcd\n}\n'
                'elf_symbol {\n  id: 0x2\n  name: "bad"\n  crc: 0x00000001\n}\n'
                'elf_symbol {\n  id: 0x3\n  name: "gone"\n  crc: 0x00000002\n}\n'
                'elf_symbol {\n  id: 0x4\n  name: "nocrc"\n}\n'
            )
        with open(sv_path, "w", encoding="utf-8") as f:
            f.write("0x0000abcd\tok\tvmlinux\tEXPORT_SYMBOL_GPL\n"
                    "0x00000009\tbad\tvmlinux\tEXPORT_SYMBOL\n")
        missing, mismatched = compare(parse_stg(stg_path), parse_symvers(sv_path))
        assert missing == ["gone"], missing
        assert mismatched == [("bad", 1, 9)], mismatched
        assert main(["x", stg_path, sv_path]) == 1
    print("self-check passed")


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-check"]:
        _self_check()
        sys.exit(0)
    sys.exit(main(sys.argv))
