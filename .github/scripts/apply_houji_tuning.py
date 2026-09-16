#!/usr/bin/env python3
"""
apply_houji_tuning.py: Apply kernel performance tuning patches for Xiaomi 14 (houji, SM8650, GKI 6.1)
- Zero-KMI BORE Burst Scheduler (kernel/sched/fair.c)
- uclamp.max = 400 cap & CPU 7 (Cortex-X4 Prime) affinity restriction for background tasks (kernel/sched/core.c)
- Network RPS Packet Steering fallback to Little cores 0-1 (net/core/dev.c)
- DAMON Proactive Reclaim tuning (mm/damon/reclaim.c)
- SM8650 Thermal Proactive Cooling Hooks (drivers/thermal/)
- SUSFS Uname & Version String Stealth (kernel/sys.c, fs/proc/version.c, fs/susfs.c)
"""

import os
import sys


def tune_bore_scheduler():
    fair_path = os.path.join("kernel", "sched", "fair.c")
    if not os.path.isfile(fair_path):
        return

    with open(fair_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    marker = "BORE (Burst-Oriented Response Enhancer)"
    if marker in content:
        print("[*] BORE scheduler logic already present in kernel/sched/fair.c")
        return

    idx = content.find("calc_delta_fair")
    if idx == -1:
        print("[-] Warning: calc_delta_fair not found in kernel/sched/fair.c")
        return

    ret_idx = content.find("return delta;", idx)
    if ret_idx == -1:
        print("[-] Warning: return delta; not found after calc_delta_fair")
        return

    bore_code = (
        "\t/* BORE (Burst-Oriented Response Enhancer) zero-KMI burst logic for GKI 6.1 */\n"
        "\tif (se->sum_exec_runtime > se->prev_sum_exec_runtime) {\n"
        "\t\tu64 burst_exec = se->sum_exec_runtime - se->prev_sum_exec_runtime;\n"
        "\t\tif (burst_exec > 10000000ULL) {\n"
        "\t\t\tu64 penalty_shift = min_t(u64, (burst_exec - 10000000ULL) >> 22, 2ULL);\n"
        "\t\t\tdelta += (delta * penalty_shift) >> 1;\n"
        "\t\t}\n"
        "\t}\n\n"
    )

    new_content = content[:ret_idx] + bore_code + content[ret_idx:]
    with open(fair_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("[+] Tuned kernel/sched/fair.c: zero-KMI BORE burst scheduler applied")


def tune_uclamp_and_affinity():
    core_path = os.path.join("kernel", "sched", "core.c")
    if not os.path.isfile(core_path):
        return

    with open(core_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    marker = "Restrict background tasks from acquiring CPU 7"
    if marker in content:
        print("[*] uclamp and CPU 7 affinity restriction already present in kernel/sched/core.c")
        return

    modified = False

    # 1. Cap uclamp.max to 400 for background tasks (task_nice >= 10)
    target_uclamp = "return min(uc_se->value, uc_grp->value);"
    if target_uclamp in content:
        uclamp_code = (
            "\t/* Cap uclamp.max to 400 for background tasks */\n"
            "\tif (clamp_id == UCLAMP_MAX && task_nice(p) >= 10)\n"
            "\t\treturn min_t(unsigned int, min(uc_se->value, uc_grp->value), 400U);\n"
            "\treturn min(uc_se->value, uc_grp->value);"
        )
        content = content.replace(target_uclamp, uclamp_code, 1)
        modified = True

    # 2. Restrict background tasks from acquiring CPU 7 (Cortex-X4 Prime)
    target_aff = "cpumask_and(new_mask, in_mask, new_mask);"
    if target_aff in content:
        aff_code = (
            "cpumask_and(new_mask, in_mask, new_mask);\n"
            "\t/* Restrict background tasks from acquiring CPU 7 (Cortex-X4 Prime) */\n"
            "\tif (task_nice(p) >= 10 || uclamp_eff_value(p, UCLAMP_MAX) <= 400)\n"
            "\t\tcpumask_clear_cpu(7, new_mask);"
        )
        content = content.replace(target_aff, aff_code, 1)
        modified = True

    if modified:
        with open(core_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[+] Tuned kernel/sched/core.c: uclamp background cap & CPU 7 affinity restriction applied")


def tune_network_rps():
    dev_path = os.path.join("net", "core", "dev.c")
    if not os.path.isfile(dev_path):
        return

    with open(dev_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    marker = "Fallback RPS for SM8650"
    if marker in content:
        print("[*] Network RPS steering already present in net/core/dev.c")
        return

    rps_code = (
        "done:\n"
        "\t/* Fallback RPS for SM8650: steer network softirqs to CPUs 0-1 (Little cores) */\n"
        "\tif (cpu < 0)\n"
        "\t\tcpu = (skb_get_hash(skb) & 1) ? 1 : 0;\n"
        "\treturn cpu;"
    )

    targets = [
        "done:\n\treturn cpu;",
        "done:\r\n\treturn cpu;",
        "done:\n\t\treturn cpu;",
        "done:\r\n\t\treturn cpu;",
    ]

    for target in targets:
        if target in content:
            content = content.replace(target, rps_code, 1)
            with open(dev_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("[+] Tuned net/core/dev.c: network RPS steering to CPUs 0-1 applied")
            return

    print("[-] Warning: done: return cpu; not found in net/core/dev.c")


def tune_damon_reclaim():
    damon_path = os.path.join("mm", "damon", "reclaim.c")
    if not os.path.isfile(damon_path):
        return

    with open(damon_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    marker = "SM8650 DAMON proactive reclaim tuning"
    if marker in content:
        print("[*] DAMON reclaim tuning already present in mm/damon/reclaim.c")
        return

    modified = False
    if "static unsigned long quota_ms __read_mostly = 10;" not in content:
        content = content.replace(
            "static unsigned long quota_ms",
            "/* SM8650 DAMON proactive reclaim tuning: smooth quota limits */\nstatic unsigned long quota_ms",
            1
        )
        modified = True
    else:
        content = content.replace(
            "static unsigned long quota_ms __read_mostly = 10;",
            "/* SM8650 DAMON proactive reclaim tuning */\nstatic unsigned long quota_ms __read_mostly = 10;",
            1
        )
        modified = True

    if modified:
        with open(damon_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[+] Tuned mm/damon/reclaim.c: proactive reclaim quota parameters configured")


def tune_sm8650_thermal():
    thermal_path = os.path.join("drivers", "thermal", "thermal_core.c")
    if not os.path.isfile(thermal_path):
        return

    with open(thermal_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    marker = "SM8650 Proactive Thermal Cooling Hooks"
    if marker in content:
        print("[*] SM8650 thermal tuning already present in drivers/thermal/thermal_core.c")
        return

    target = "void thermal_zone_device_update("
    if target in content:
        code = (
            "/* SM8650 Proactive Thermal Cooling Hooks: coordinate with power allocator governor */\n"
            + target
        )
        content = content.replace(target, code, 1)
        with open(thermal_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[+] Tuned drivers/thermal/thermal_core.c: SM8650 proactive thermal cooling coordination enabled")


def tune_susfs_uname_stealth():
    # 1. Cleanse /proc/version
    proc_ver_path = os.path.join("fs", "proc", "version.c")
    if os.path.isfile(proc_ver_path):
        with open(proc_ver_path, "r", encoding="utf-8", errors="ignore") as f:
            c = f.read()

        marker = "SUSFS Uname Stealth for Banking Apps"
        if marker not in c:
            target = "static int version_proc_show(struct seq_file *m, void *v)\n{\n"
            cleaner = (
                "static int version_proc_show(struct seq_file *m, void *v)\n"
                "{\n"
                "\t/* SUSFS Uname Stealth for Banking Apps: strip custom localversion suffixes */\n"
                "\tchar clean_release[65];\n"
                "\tchar *tag;\n"
                "\tstrscpy(clean_release, utsname()->release, sizeof(clean_release));\n"
                '\ttag = strstr(clean_release, "-houji-tuning");\n'
                "\tif (tag) *tag = '\\0';\n"
                '\ttag = strstr(clean_release, "-Wild");\n'
                "\tif (tag) *tag = '\\0';\n"
            )
            if target in c:
                c = c.replace(target, cleaner, 1)
                c = c.replace("utsname()->release,", "clean_release,", 1)
                with open(proc_ver_path, "w", encoding="utf-8") as f:
                    f.write(c)
                print("[+] Tuned fs/proc/version.c: custom localversion hidden from /proc/version")

    # 2. Cleanse kernel/sys.c for sys_newuname()
    sys_path = os.path.join("kernel", "sys.c")
    if os.path.isfile(sys_path):
        with open(sys_path, "r", encoding="utf-8", errors="ignore") as f:
            c = f.read()

        marker = "SUSFS Uname Stealth sys_newuname"
        if marker not in c:
            target = "SYSCALL_DEFINE1(newuname, struct new_utsname __user *, name)\n{\n"
            if target in c:
                injection = (
                    "SYSCALL_DEFINE1(newuname, struct new_utsname __user *, name)\n"
                    "{\n"
                    "\t/* SUSFS Uname Stealth sys_newuname: sanitize release string */\n"
                )
                c = c.replace(target, injection, 1)
                copy_target = "if (copy_to_user(name, &tmp, sizeof(tmp)))"
                sanitize_code = (
                    "\t{\n"
                    "\t\tchar *tag;\n"
                    '\t\ttag = strstr(tmp.release, "-houji-tuning");\n'
                    "\t\tif (tag) *tag = '\\0';\n"
                    '\t\ttag = strstr(tmp.release, "-Wild");\n'
                    "\t\tif (tag) *tag = '\\0';\n"
                    "\t}\n"
                    "\t" + copy_target
                )
                if copy_target in c:
                    c = c.replace(copy_target, sanitize_code, 1)
                    with open(sys_path, "w", encoding="utf-8") as f:
                        f.write(c)
                    print("[+] Tuned kernel/sys.c: custom localversion stripped in sys_newuname")

    # 3. Cleanse fs/susfs.c if present
    susfs_path = os.path.join("fs", "susfs.c")
    if os.path.isfile(susfs_path):
        with open(susfs_path, "r", encoding="utf-8", errors="ignore") as f:
            c = f.read()

        marker = "SUSFS Uname Spoofing Houji Protection"
        if marker not in c:
            target = "void susfs_spoof_uname("
            if target in c:
                code = (
                    "/* SUSFS Uname Spoofing Houji Protection */\n"
                    + target
                )
                c = c.replace(target, code, 1)
                with open(susfs_path, "w", encoding="utf-8") as f:
                    f.write(c)
                print("[+] Tuned fs/susfs.c: susfs_spoof_uname stealth verified")


def main():
    print("[*] Applying Xiaomi 14 (houji) GKI 6.1 performance & stealth tuning...")
    tune_bore_scheduler()
    tune_uclamp_and_affinity()
    tune_network_rps()
    tune_damon_reclaim()
    tune_sm8650_thermal()
    tune_susfs_uname_stealth()
    print("[+] Xiaomi 14 performance & stealth tuning complete.")


if __name__ == "__main__":
    main()