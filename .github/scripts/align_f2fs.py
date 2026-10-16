#!/usr/bin/env python3
"""
Align F2FS struct ABI layout for Xiaomi HyperOS vendor module compatibility (Zero Black Screen).

Google's zoned block device commits inserted fields into struct f2fs_mount_info and struct f2fs_sb_info,
which shifts iostat_lock / iostat_io_lat accessed by Xiaomi's prebuilt vendor modules (mi_ext_lru.ko).
This script relocates those 3 fields to the end of struct f2fs_sb_info to preserve 100% ABI offset compatibility.
"""

import sys
from pathlib import Path


def main():
    kernel_dir = Path.cwd()
    f2fs_h = kernel_dir / "fs" / "f2fs" / "f2fs.h"
    super_c = kernel_dir / "fs" / "f2fs" / "super.c"

    if not f2fs_h.exists():
        print(f"[*] {f2fs_h} not found, skipping F2FS alignment.")
        return 0

    c = f2fs_h.read_text(encoding="utf-8")
    if "unsigned int resizable_tail_secno;" not in c:
        print("[*] F2FS struct alignment not needed (fields already absent).")
        return 0

    c = c.replace("\tunsigned int resizable_tail_secno;\t/* number of resizable tail sections */\n", "")
    c = c.replace("\tunsigned int first_seq_zone_segno;\t/* first segno in sequential zone */\n", "")
    c = c.replace("\tunsigned int pinned_area_max_secno;\t/* upper bound section for pinned files */\n", "")

    target = "\tstruct iostat_lat_info *iostat_io_lat;\n#endif\n};"
    replacement = (
        "\tstruct iostat_lat_info *iostat_io_lat;\n"
        "#endif\n"
        "\t/* ABI pad for Xiaomi vendor module compatibility */\n"
        "\tunsigned int first_seq_zone_segno;\n"
        "\tunsigned int pinned_area_max_secno;\n"
        "\tunsigned int resizable_tail_secno;\n"
        "};"
    )

    if target in c:
        c = c.replace(target, replacement)
        f2fs_h.write_text(c, encoding="utf-8")

        if super_c.exists():
            s = super_c.read_text(encoding="utf-8")
            s = s.replace("F2FS_OPTION(sbi).resizable_tail_secno", "sbi->resizable_tail_secno")
            super_c.write_text(s, encoding="utf-8")

        print("[+] F2FS struct layout successfully aligned for Xiaomi HyperOS vendor modules!")
    else:
        print("[-] Target pattern not found in f2fs.h, skipping.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
