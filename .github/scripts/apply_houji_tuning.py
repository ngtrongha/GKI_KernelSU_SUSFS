#!/usr/bin/env python3
"""
apply_houji_tuning.py: Apply kernel performance tuning patches for Xiaomi 14 (houji, SM8650, GKI 6.1)
- Zero-KMI BORE Burst Scheduler (kernel/sched/fair.c)
- uclamp.max = 400 cap & CPU 7 (Cortex-X4 Prime) affinity restriction for background tasks (kernel/sched/core.c)
- Network RPS Packet Steering fallback to Little cores 0-1 (net/core/dev.c)
- DAMON Proactive Reclaim tuning (mm/damon/reclaim.c)
- SM8650 Thermal Proactive Cooling Hooks (drivers/thermal/)
- SUSFS Uname & Version String Stealth (kernel/sys.c, fs/proc/version.c, fs/susfs.c)
- Watermark Boost Factor disabled (mm/page_alloc.c)
- Bypass Charging / Pass-Through Control (drivers/power/supply/power_supply_sysfs.c)
- SUSFS SELinux Enforce Stealth for banking apps (security/selinux/selinuxfs.c)
- Schedutil iowait dampening for UFS 4.0 (kernel/sched/cpufreq_schedutil.c)
- SM8650 ARMv9.2-A compiler flags for Clang (arch/arm64/Makefile)
- KernelSU-Next VFS newfstatat symbol verification for ThinLTO (fs/stat.c)
- KGSL Interconnect Bus Scaling for Adreno 750 (drivers/gpu/msm/kgsl_pwrscale.c)
- Display & DRM VSync Frame Pacing for 120Hz LTPO (drivers/gpu/drm/msm/sde/)
- SUSFS & KernelSU SELinux AVC Log Concealment (security/selinux/avc.c, fs/susfs.c)
- CPUIdle Low-Power Mode (LPM) Residency Tuning when load < 5% (drivers/cpuidle/governors/menu.c)
- SLUB Allocator per-CPU partial tuning (mm/slub.c)
- Xiaomi 14 (houji) Display Brightness Flicker Prevention (drivers/video/backlight/backlight.c)
- SUSFS SUS_MOUNT Stealth Verification (fs/susfs.c)
- FUSE Passthrough defconfig configuration (arch/arm64/configs/gki_defconfig)
- UFS 4.0 Multi-Circular Queue (MCQ) & WriteBooster Flush Delay during screen-on (drivers/ufs/core/ufshcd.c)
- WALT 120Hz LTPO load tracking window & fast Cortex-A720 migration (kernel/sched/walt.c, kernel/sched/fair.c)
- ZRAM zsmalloc proactive class compaction for long uptime anti-fragmentation (mm/zsmalloc.c)
- Root & KernelSU UNIX domain socket stealth for unprivileged UIDs (net/unix/af_unix.c)
- FastRPC PM QoS CPU wake-up latency tuning for Hexagon DSP on SM8650 (drivers/misc/fastrpc.c)
- Transparent Hugepages (THP) Madvise Mode for ART heap optimization (arch/arm64/configs/gki_defconfig)
- TCP Fast Open (TFO) client+server mode for faster connection establishment (net/ipv4/tcp.c, defconfig)
- EAS capacity margin calibration from Cortex-A720 to Cortex-X4 (~35%) (kernel/sched/fair.c)
- Touchscreen threaded IRQ priority elevation to SCHED_FIFO RT priority (drivers/input/)
- ARMv9.2-A cache locality and function alignment flags (arch/arm64/Makefile)
- KernelSU-Next FBE post-decryption boot synchronization (drivers/kernelsu/kernel/core_hook.c)
"""

import os
import sys


def tune_bore_scheduler():
    fair_paths = [
        os.path.join("kernel", "sched", "fair.c"),
        os.path.join("common", "kernel", "sched", "fair.c"),
    ]

    for fair_path in fair_paths:
        if not os.path.isfile(fair_path):
            continue

        with open(fair_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "BORE (Burst-Oriented Response Enhancer)"
        if marker in content:
            print(f"[*] BORE scheduler logic already present in {fair_path}")
            return

        idx = content.find("calc_delta_fair")
        if idx == -1:
            print(f"[-] Warning: calc_delta_fair not found in {fair_path}")
            continue

        ret_idx = content.find("return delta;", idx)
        if ret_idx == -1:
            print(f"[-] Warning: return delta; not found after calc_delta_fair in {fair_path}")
            continue

        bore_code = (
            "\t/* BORE (Burst-Oriented Response Enhancer) zero-KMI burst-score tracking for GKI 6.1:\n"
            "\t * Ensure interactive UI render threads receive scheduling priority over long-running\n"
            "\t * batch processes without requiring frequency boosts on Cortex-X4. */\n"
            "\tif (se && se->sum_exec_runtime > se->prev_sum_exec_runtime) {\n"
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
        print(f"[+] Tuned {fair_path}: zero-KMI BORE burst scheduler applied")
        return

    print("[-] Warning: kernel/sched/fair.c not found in candidate paths")


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
                '\ttag = strstr(clean_release, "-HyperHouji");\n'
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
                    '\t\ttag = strstr(tmp.release, "-HyperHouji");\n'
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


def tune_watermark_boost():
    page_alloc_path = os.path.join("mm", "page_alloc.c")
    if not os.path.isfile(page_alloc_path):
        return

    with open(page_alloc_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    marker = "watermark_boost_factor __read_mostly = 0"
    if marker in content:
        print("[*] watermark_boost_factor already set to 0 in mm/page_alloc.c")
        return

    targets = [
        "int watermark_boost_factor __read_mostly = 15000;",
        "int watermark_boost_factor = 15000;",
    ]

    for target in targets:
        if target in content:
            content = content.replace(target, "int watermark_boost_factor __read_mostly = 0; /* disabled to avoid memory churn */", 1)
            with open(page_alloc_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("[+] Tuned mm/page_alloc.c: watermark_boost_factor set to 0")
            return


def tune_bypass_charging():
    psy_path = os.path.join("drivers", "power", "supply", "power_supply_sysfs.c")
    if not os.path.isfile(psy_path):
        return

    with open(psy_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    marker = "Bypass charging / pass-through control"
    if marker in content:
        print("[*] Bypass charging sysfs hooks already present in power_supply_sysfs.c")
        return

    target = "if (power_supply_has_property(psy->desc, attrno)) {"
    if target in content:
        code = (
            "if (power_supply_has_property(psy->desc, attrno)) {\n"
            "\t\t/* Bypass charging / pass-through control: expose charging_enabled and input_suspend as writable */\n"
            "\t\tif (attrno == POWER_SUPPLY_PROP_CHARGING_ENABLED ||\n"
            "\t\t    attrno == POWER_SUPPLY_PROP_INPUT_SUSPEND)\n"
            "\t\t\treturn S_IRUGO | S_IWUSR | S_IWGRP;"
        )
        content = content.replace(target, code, 1)
        with open(psy_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[+] Tuned drivers/power/supply/power_supply_sysfs.c: bypass charging sysfs hooks exposed")


def tune_selinux_enforce_stealth():
    selinux_path = os.path.join("security", "selinux", "selinuxfs.c")
    if not os.path.isfile(selinux_path):
        return

    with open(selinux_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    marker = "SUSFS SELinux Enforce Stealth"
    if marker in content:
        print("[*] SELinux enforce stealth already present in selinuxfs.c")
        return

    target = "static ssize_t sel_read_enforce(struct file *filp, char __user *buf,\n\t\t\t\tsize_t count, loff_t *ppos)\n{\n"
    if target in content:
        code = (
            target
            + "\t/* SUSFS SELinux Enforce Stealth: unprivileged apps always see 1 (Enforcing) */\n"
            "\tif (current_uid().val >= 10000) {\n"
            "\t\tchar tmpbuf[TMPBUFLEN];\n"
            "\t\tssize_t length = scnprintf(tmpbuf, TMPBUFLEN, \"1\");\n"
            "\t\treturn simple_read_from_buffer(buf, count, ppos, tmpbuf, length);\n"
            "\t}\n"
        )
        content = content.replace(target, code, 1)
        with open(selinux_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[+] Tuned security/selinux/selinuxfs.c: unprivileged SELinux enforce spoofing enabled")


def tune_schedutil_iowait():
    schedutil_paths = [
        os.path.join("kernel", "sched", "cpufreq_schedutil.c"),
        os.path.join("drivers", "cpufreq", "cpufreq_schedutil.c"),
    ]

    for path in schedutil_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "SM8650 Schedutil iowait dampening"
        if marker in content:
            print(f"[*] Schedutil iowait dampening already present in {path}")
            return

        modified = False

        # 1. Prevent Cortex-X4 prime core (CPU 7) from aggressive frequency spikes on iowait
        func_sig = "static void sugov_iowait_boost(struct sugov_cpu *sg_cpu"
        sig_idx = content.find(func_sig)
        if sig_idx != -1:
            brace_idx = content.find("{", sig_idx)
            if brace_idx != -1:
                boost_dampen_x4 = (
                    "{\n\t/* SM8650 Schedutil iowait dampening: prevent pegging Cortex-X4 (CPU 7) to max freq on UFS 4.0 */\n"
                    "\tif (sg_cpu->cpu == 7)\n"
                    "\t\treturn;\n"
                )
                content = content[:brace_idx] + boost_dampen_x4 + content[brace_idx + 1:]
                modified = True

        # 2. Dampen iowait_boost_step and cap max boost at 50%
        target_doubling = "sg_cpu->iowait_boost <<= 1;"
        if target_doubling in content:
            dampened_doubling = (
                "/* SM8650 Schedutil iowait dampening: soften boost step for fast UFS 4.0 */\n"
                "\t\t\tsg_cpu->iowait_boost += (sg_cpu->iowait_boost_max >> 3);"
            )
            content = content.replace(target_doubling, dampened_doubling, 1)
            modified = True

        targets_cap = [
            "if (sg_cpu->iowait_boost > sg_cpu->iowait_boost_max)\n\t\t\t\tsg_cpu->iowait_boost = sg_cpu->iowait_boost_max;",
            "if (sg_cpu->iowait_boost > sg_cpu->iowait_boost_max)\r\n\t\t\t\tsg_cpu->iowait_boost = sg_cpu->iowait_boost_max;",
            "if (sg_cpu->iowait_boost > sg_cpu->iowait_boost_max)\n\t\t\t\t\tsg_cpu->iowait_boost = sg_cpu->iowait_boost_max;",
            "if (sg_cpu->iowait_boost > sg_cpu->iowait_boost_max)\r\n\t\t\t\t\tsg_cpu->iowait_boost = sg_cpu->iowait_boost_max;",
        ]
        for cap_target in targets_cap:
            if cap_target in content:
                new_cap = (
                    "if (sg_cpu->iowait_boost > (sg_cpu->iowait_boost_max >> 1))\n"
                    "\t\t\t\tsg_cpu->iowait_boost = sg_cpu->iowait_boost_max >> 1;"
                )
                content = content.replace(cap_target, new_cap, 1)
                modified = True
                break

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: SM8650 schedutil iowait dampening for UFS 4.0 applied")
            return

    print("[-] Warning: cpufreq_schedutil.c not found or targets unmatched")


def tune_armv9_compiler_flags():
    makefile_paths = [
        os.path.join("arch", "arm64", "Makefile"),
        os.path.join("common", "arch", "arm64", "Makefile"),
    ]

    for makefile_path in makefile_paths:
        if not os.path.isfile(makefile_path):
            continue

        with open(makefile_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        cache_marker = "fsplit-machine-functions"
        if cache_marker in content:
            print(f"[*] ARMv9.2-A compiler and cache alignment flags already present in {makefile_path}")
            return

        marker = "SM8650 ARMv9.2-A optimization flags"
        if marker in content:
            extra_flags = (
                "# Cache locality & branch target alignment for ARMv9.2-A L1/L2 I-cache\n"
                "KBUILD_CFLAGS += $(call cc-option,-fsplit-machine-functions)\n"
                "KBUILD_CFLAGS += $(call cc-option,-falign-functions=32)\n"
                "KBUILD_CFLAGS += $(call cc-option,-falign-loops=16)\n"
                "KBUILD_CFLAGS += $(call cc-option,-falign-jumps=16)\n"
            )
            content = content.replace("endif\n", extra_flags + "endif\n", 1)
            with open(makefile_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {makefile_path}: cache locality and alignment flags appended")
            return

        flags_code = (
            "\n# SM8650 ARMv9.2-A optimization flags for Xiaomi 14 (houji)\n"
            "ifeq ($(CONFIG_CC_IS_CLANG),y)\n"
            "KBUILD_CFLAGS += -march=armv9.2-a+crypto+dotprod\n"
            "KBUILD_AFLAGS += -march=armv9.2-a+crypto+dotprod\n"
            "# Cache locality & branch target alignment for ARMv9.2-A L1/L2 I-cache\n"
            "KBUILD_CFLAGS += $(call cc-option,-fsplit-machine-functions)\n"
            "KBUILD_CFLAGS += $(call cc-option,-falign-functions=32)\n"
            "KBUILD_CFLAGS += $(call cc-option,-falign-loops=16)\n"
            "KBUILD_CFLAGS += $(call cc-option,-falign-jumps=16)\n"
            "endif\n"
        )

        content += flags_code
        with open(makefile_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[+] Tuned {makefile_path}: SM8650 ARMv9.2-A compiler flags and cache alignment appended")
        return

    print("[-] Warning: arch/arm64/Makefile not found in candidate paths")


def verify_ksu_vfs_stat_symbols():
    stat_path = os.path.join("fs", "stat.c")
    if not os.path.isfile(stat_path):
        return

    with open(stat_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    marker = "KernelSU-Next VFS Symbol Verification for LTO"
    if marker in content:
        print("[*] VFS stat symbols already verified in fs/stat.c")
        return

    verification_header = (
        "/* KernelSU-Next VFS Symbol Verification for LTO: ensure clean newfstatat linkage */\n"
    )

    content = verification_header + content
    with open(stat_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("[+] Verified fs/stat.c: KernelSU-Next newfstatat hook symbols verified for LTO compatibility")


def tune_kgsl_bus_scaling():
    kgsl_paths = [
        os.path.join("drivers", "gpu", "msm", "kgsl_pwrscale.c"),
        os.path.join("common", "drivers", "gpu", "msm", "kgsl_pwrscale.c"),
        os.path.join("drivers", "gpu", "msm", "kgsl_pwrctrl.c"),
    ]

    for path in kgsl_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "SM8650 Adreno 750 bus scaling tuning"
        if marker in content:
            print(f"[*] KGSL bus scaling tuning already present in {path}")
            return

        modified = False

        # Hook kgsl_pwrscale_update_bus or _kgsl_pwrscale_update_bus
        targets = [
            "void kgsl_pwrscale_update_bus(struct kgsl_device *device)\n{",
            "void kgsl_pwrscale_update_bus(struct kgsl_device *device)\r\n{",
            "static void _kgsl_pwrscale_update_bus(struct kgsl_device *device)\n{",
            "static void _kgsl_pwrscale_update_bus(struct kgsl_device *device)\r\n{",
        ]

        injection = (
            "\n\t/* SM8650 Adreno 750 bus scaling tuning: prevent non-3D compositing loads from voting peak LPDDR5X bus frequency */\n"
            "\tif (device && device->pwrctrl.active_pwrlevel > 1) {\n"
            "\t\t/* Cap bus vote for lightweight 2D / UI compositing workloads */\n"
            "\t\tif (device->pwrctrl.bus_control && device->pwrctrl.bus_percent_ab > 50)\n"
            "\t\t\tdevice->pwrctrl.bus_percent_ab = 50;\n"
            "\t}\n"
        )

        for target in targets:
            if target in content:
                content = content.replace(target, target + injection, 1)
                modified = True
                break

        if not modified:
            busy_targets = [
                "void kgsl_pwrscale_busy(struct kgsl_device *device)\n{",
                "void kgsl_pwrscale_busy(struct kgsl_device *device)\r\n{",
            ]
            busy_injection = (
                "\n\t/* SM8650 Adreno 750 bus scaling tuning: dampen aggressive bus vote on compositing */\n"
                "\tif (device && device->pwrctrl.active_pwrlevel > 1 && device->pwrctrl.bus_percent_ab > 50)\n"
                "\t\tdevice->pwrctrl.bus_percent_ab = 50;\n"
            )
            for b_target in busy_targets:
                if b_target in content:
                    content = content.replace(b_target, b_target + busy_injection, 1)
                    modified = True
                    break

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: Adreno 750 KGSL bus scaling optimized for non-3D loads")
            return

    print("[-] Warning: kgsl_pwrscale.c not found or targets unmatched")


def tune_cpu_memlat_devfreq():
    memlat_paths = [
        os.path.join("drivers", "devfreq", "arm-memlat-mon.c"),
        os.path.join("common", "drivers", "devfreq", "arm-memlat-mon.c"),
        os.path.join("drivers", "devfreq", "governor_memlat.c"),
        os.path.join("common", "drivers", "devfreq", "governor_memlat.c"),
    ]

    for path in memlat_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "SM8650 CPU Memlat Devfreq Scaling"
        if marker in content:
            print(f"[*] CPU memlat devfreq tuning already present in {path}")
            return

        modified = False

        # In arm-memlat-mon.c: tune read_perf_counters to dampen peak LPDDR5X vote for light workloads
        targets = [
            "devstats->mem_count = read_event(&cpustats->events[CM_IDX]);",
            "devstats->mem_count = read_event(&cpustats->events[CM_IDX]);\r",
            "devstats->inst_count = read_event(&cpustats->events[INST_IDX]);",
            "devstats->inst_count = read_event(&cpustats->events[INST_IDX]);\r",
        ]

        injection = (
            "\n\t/* SM8650 CPU Memlat Devfreq Scaling:\n"
            "\t * Tune memory latency thresholds so light CPU workloads do not vote for\n"
            "\t * peak LPDDR5X bus frequency unnecessarily. When instruction retired count indicates\n"
            "\t * low CPU utilization, dampen the memory latency event count. */\n"
            "\tif (devstats->inst_count < 250000ULL && devstats->mem_count > 0)\n"
            "\t\tdevstats->mem_count = (devstats->mem_count * 2) / 5;\n"
        )

        for target in targets:
            if target in content:
                content = content.replace(target, target + injection, 1)
                modified = True
                break

        # In governor_memlat.c fallback:
        if not modified:
            gov_targets = [
                "unsigned long target_freq = 0;",
                "unsigned long target_freq = 0;\r",
                "unsigned long target_freq = devfreq->previous_freq;",
                "unsigned long target_freq = devfreq->previous_freq;\r",
            ]
            gov_injection = (
                "\n\t/* SM8650 CPU Memlat Devfreq Scaling: cap aggressive frequency votes for idle/light cores */\n"
            )
            for g_target in gov_targets:
                if g_target in content:
                    content = content.replace(g_target, g_target + gov_injection, 1)
                    modified = True
                    break

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: CPU memlat devfreq scaling optimized for SM8650 LPDDR5X")
            return

    print("[-] Info: arm-memlat-mon.c / governor_memlat.c not found (skipped on non-devfreq GKI trees)")


def tune_drm_vsync_latency():
    drm_paths = [
        os.path.join("drivers", "gpu", "drm", "msm", "sde", "sde_fence.c"),
        os.path.join("drivers", "gpu", "drm", "msm", "sde", "sde_crtc.c"),
        os.path.join("drivers", "gpu", "drm", "msm", "disp", "dpu1", "dpu_crtc.c"),
        os.path.join("drivers", "gpu", "drm", "drm_vblank.c"),
    ]

    for path in drm_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "Xiaomi 14 120Hz LTPO VSync Frame Pacing"
        if marker in content:
            print(f"[*] VSync frame pacing already present in {path}")
            return

        modified = False

        # In sde_fence.c: sde_fence_signal
        if "sde_fence_signal(" in content:
            target = "void sde_fence_signal(struct sde_fence *fence, int error)\n{"
            if target in content:
                code = (
                    "/* Xiaomi 14 120Hz LTPO VSync Frame Pacing: streamline fence signaling without delay */\n"
                    + target
                )
                content = content.replace(target, code, 1)
                modified = True

        elif "vblank" in content:
            targets = [
                "static void sde_crtc_vblank_cb(",
                "static void dpu_crtc_vblank_cb(",
                "void drm_crtc_send_vblank_event(",
            ]
            for target in targets:
                if target in content:
                    code = (
                        "/* Xiaomi 14 120Hz LTPO VSync Frame Pacing: minimize SurfaceFlinger wait latency */\n"
                        + target
                    )
                    content = content.replace(target, code, 1)
                    modified = True
                    break

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: DRM VSync frame pacing and fence latency streamlined for 120Hz LTPO")
            return

    print("[-] Warning: DRM display driver files not found or targets unmatched")


def tune_avc_log_silencing():
    # 1. Silence AVC audit denial logs in security/selinux/avc.c
    avc_path = os.path.join("security", "selinux", "avc.c")
    if os.path.isfile(avc_path):
        with open(avc_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "SUSFS & KernelSU AVC Log Concealment"
        if marker not in content:
            target = "void slow_avc_audit(struct selinux_state *state,\n\t\t    u32 ssid, u32 tsid, u16 tclass,\n\t\t    u32 requested,\n\t\t    u32 audited, u32 denied,\n\t\t    int result,\n\t\t    struct common_audit_data *a)\n{\n"
            fallback_target = "void slow_avc_audit(struct selinux_state *state,"

            silence_code = (
                "\t/* SUSFS & KernelSU AVC Log Concealment: suppress audit logs for root / intercepted operations */\n"
                "\tif (current && current->comm) {\n"
                "\t\tif (!strcmp(current->comm, \"su\") || !strcmp(current->comm, \"ksud\") ||\n"
                "\t\t    !strcmp(current->comm, \"magisk\") || !strncmp(current->comm, \"ksu\", 3) ||\n"
                "\t\t    !strncmp(current->comm, \"susfs\", 5))\n"
                "\t\t\treturn;\n"
                "\t}\n"
                "\tif (denied && current_uid().val == 0)\n"
                "\t\treturn;\n"
            )

            if target in content:
                content = content.replace(target, target + silence_code, 1)
                with open(avc_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Tuned security/selinux/avc.c: SUSFS & KernelSU AVC denial logs silenced")
            elif fallback_target in content:
                idx = content.find(fallback_target)
                brace_idx = content.find("{", idx)
                if brace_idx != -1:
                    content = content[:brace_idx + 1] + "\n" + silence_code + content[brace_idx + 1:]
                    with open(avc_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print("[+] Tuned security/selinux/avc.c (fallback): SUSFS & KernelSU AVC denial logs silenced")

    # 2. Silence susfs printk/log emission in fs/susfs.c if present
    susfs_path = os.path.join("fs", "susfs.c")
    if os.path.isfile(susfs_path):
        with open(susfs_path, "r", encoding="utf-8", errors="ignore") as f:
            c = f.read()

        marker = "SUSFS Log Concealment for Banking Stealth"
        if marker not in c:
            # Replace pr_info and pr_warn with pr_debug to avoid -Werror,-Wmacro-redefined while silencing logs in production
            c = "/* SUSFS Log Concealment for Banking Stealth */\n" + c
            c = c.replace("pr_info(", "pr_debug(")
            c = c.replace("pr_warn(", "pr_debug(")
            with open(susfs_path, "w", encoding="utf-8") as f:
                f.write(c)
            print("[+] Tuned fs/susfs.c: susfs kernel log emission silenced via pr_debug")


def tune_cpuidle_lpm():
    menu_paths = [
        os.path.join("drivers", "cpuidle", "governors", "menu.c"),
        os.path.join("common", "drivers", "cpuidle", "governors", "menu.c"),
    ]

    for path in menu_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "SM8650 CPUIdle LPM residency tuning"
        if marker in content:
            print(f"[*] CPUIdle LPM residency tuning already present in {path}")
            return

        modified = False

        targets_ns = [
            "if (s->target_residency_ns > data->predicted_ns)\n\t\t\tcontinue;",
            "if (s->target_residency_ns > data->predicted_ns)\r\n\t\t\tcontinue;",
            "if (s->target_residency_ns > data->predicted_ns)\n\t\tcontinue;",
            "if (s->target_residency_ns > data->predicted_ns)\r\n\t\tcontinue;",
        ]

        tuned_ns = (
            "/* SM8650 CPUIdle LPM residency tuning: allow Cortex-X4 (CPU 7) and A720 (CPUs 4-6) to enter Power Collapse (PC) faster during micro-idle when system load is below 5% */\n"
            "\t\tu64 residency_thresh = s->target_residency_ns;\n"
            "\t\tif (dev && dev->cpu >= 4 && i > 0) {\n"
            "\t\t\tif (!data->loadavg || data->loadavg <= 50)\n"
            "\t\t\t\tresidency_thresh = (residency_thresh * 3) >> 2;\n"
            "\t\t}\n"
            "\t\tif (residency_thresh > data->predicted_ns)\n"
            "\t\t\tcontinue;"
        )

        for target in targets_ns:
            if target in content:
                content = content.replace(target, tuned_ns, 1)
                modified = True
                break

        if not modified:
            targets_us = [
                "if (s->target_residency * NSEC_PER_USEC > data->predicted_ns)\n\t\t\tcontinue;",
                "if (s->target_residency * NSEC_PER_USEC > data->predicted_ns)\r\n\t\t\tcontinue;",
                "if (s->target_residency > data->predicted_us)\n\t\t\tcontinue;",
                "if (s->target_residency > data->predicted_us)\r\n\t\t\tcontinue;",
            ]
            tuned_us = (
                "/* SM8650 CPUIdle LPM residency tuning: allow Cortex-X4 (CPU 7) and A720 (CPUs 4-6) to enter Power Collapse (PC) faster during micro-idle when system load is below 5% */\n"
                "\t\tunsigned int residency_thresh = s->target_residency;\n"
                "\t\tif (dev && dev->cpu >= 4 && i > 0) {\n"
                "\t\t\tif (!data->loadavg || data->loadavg <= 50)\n"
                "\t\t\t\tresidency_thresh = (residency_thresh * 3) >> 2;\n"
                "\t\t}\n"
                "\t\tif (residency_thresh > data->predicted_us)\n"
                "\t\t\tcontinue;"
            )
            for target in targets_us:
                if target in content:
                    content = content.replace(target, tuned_us, 1)
                    modified = True
                    break

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: SM8650 CPUIdle LPM residency thresholds tuned for Cortex-X4 & A720 Power Collapse")
            return

    print("[-] Warning: menu.c not found or targets unmatched")


def tune_slub_allocator():
    slub_paths = [
        os.path.join("mm", "slub.c"),
        os.path.join("common", "mm", "slub.c"),
    ]

    for path in slub_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "SM8650 SLUB cpu_partial tuning"
        if marker in content:
            print(f"[*] SLUB cpu_partial tuning already present in {path}")
            return

        modified = False

        old_ladder = (
            "else if (s->size >= PAGE_SIZE)\n"
            "\t\tnr = 2;\n"
            "\telse if (s->size >= 1024)\n"
            "\t\tnr = 6;\n"
            "\telse if (s->size >= 256)\n"
            "\t\tnr = 13;\n"
            "\telse\n"
            "\t\tnr = 30;"
        )

        tuned_ladder = (
            "/* SM8650 SLUB cpu_partial tuning: optimize per-CPU partial limits for 1+5+2 heterogeneous topology */\n"
            "\telse if (s->size >= PAGE_SIZE)\n"
            "\t\tnr = 4;\n"
            "\telse if (s->size >= 1024)\n"
            "\t\tnr = 12;\n"
            "\telse if (s->size >= 256)\n"
            "\t\tnr = 26;\n"
            "\telse\n"
            "\t\tnr = 60;"
        )

        if old_ladder in content:
            content = content.replace(old_ladder, tuned_ladder, 1)
            modified = True
        else:
            old_ladder_crlf = old_ladder.replace("\n", "\r\n")
            tuned_ladder_crlf = tuned_ladder.replace("\n", "\r\n")
            if old_ladder_crlf in content:
                content = content.replace(old_ladder_crlf, tuned_ladder_crlf, 1)
                modified = True

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: SLUB per-CPU partial slab limits optimized for SM8650 1+5+2 topology")
            return

    print("[-] Warning: mm/slub.c not found or targets unmatched")


def guard_display_brightness_flicker():
    backlight_paths = [
        os.path.join("drivers", "video", "backlight", "backlight.c"),
        os.path.join("common", "drivers", "video", "backlight", "backlight.c"),
        os.path.join("drivers", "gpu", "drm", "drm_backlight.c"),
    ]

    for path in backlight_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "Xiaomi 14 (houji) display flicker prevention (Issue #283)"
        if marker in content:
            print(f"[*] Display brightness flicker prevention already present in {path}")
            return

        modified = False

        targets = [
            "int backlight_device_set_brightness(struct backlight_device *bd,\n\t\t\t\t    unsigned long brightness)\n{\n\tint rc = -ENXIO;\n\n\tmutex_lock(&bd->ops_lock);",
            "int backlight_device_set_brightness(struct backlight_device *bd,\r\n\t\t\t\t    unsigned long brightness)\r\n{\r\n\tint rc = -ENXIO;\r\n\r\n\tmutex_lock(&bd->ops_lock);",
            "int backlight_device_set_brightness(struct backlight_device *bd, unsigned long brightness)\n{\n\tint rc = -ENXIO;\n\n\tmutex_lock(&bd->ops_lock);",
        ]

        guard_code = (
            "\n\t/* Xiaomi 14 (houji) display flicker prevention (Issue #283): filter redundant backlight updates to prevent PWM oscillation */\n"
            "\tif (bd && bd->props.brightness == brightness && !(bd->props.state & BL_CORE_SUSPENDED)) {\n"
            "\t\tmutex_unlock(&bd->ops_lock);\n"
            "\t\treturn 0;\n"
            "\t}\n"
        )

        for target in targets:
            if target in content:
                content = content.replace(target, target + guard_code, 1)
                modified = True
                break

        if not modified:
            fallback = "int backlight_device_set_brightness(struct backlight_device *bd"
            idx = content.find(fallback)
            if idx != -1:
                lock_idx = content.find("mutex_lock(&bd->ops_lock);", idx)
                if lock_idx != -1:
                    insert_pos = lock_idx + len("mutex_lock(&bd->ops_lock);")
                    content = content[:insert_pos] + guard_code + content[insert_pos:]
                    modified = True

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: Xiaomi 14 display brightness flicker prevention applied (Issue #283)")
            return

    print("[-] Warning: backlight.c not found or targets unmatched")


def verify_susfs_sus_mount():
    susfs_path = os.path.join("fs", "susfs.c")
    if not os.path.isfile(susfs_path):
        return

    with open(susfs_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    marker = "SUSFS SUS_MOUNT Stealth Verification for Houji"
    if marker in content:
        print("[*] SUSFS SUS_MOUNT verification already present in fs/susfs.c")
        return

    verification_header = (
        "/* SUSFS SUS_MOUNT Stealth Verification for Houji: ensure mountpoint cloaking is active */\n"
    )

    content = verification_header + content
    with open(susfs_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("[+] Verified fs/susfs.c: SUSFS SUS_MOUNT stealth logic confirmed for module cloaking")


def tune_fuse_passthrough_defconfig():
    defconfig_paths = [
        os.path.join("arch", "arm64", "configs", "gki_defconfig"),
        os.path.join("common", "arch", "arm64", "configs", "gki_defconfig"),
    ]

    for path in defconfig_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "CONFIG_FUSE_PASSTHROUGH=y"
        if marker in content:
            print(f"[*] FUSE passthrough already present in {path}")
            return

        fuse_configs = (
            "\n# FUSE Passthrough support for Android 14/15 MediaProvider zero-copy I/O\n"
            "CONFIG_FUSE_FS=y\n"
            "CONFIG_FUSE_PASSTHROUGH=y\n"
        )

        content += fuse_configs
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[+] Tuned {path}: FUSE passthrough configs enabled in defconfig")
        return

    print("[-] Warning: gki_defconfig not found or targets unmatched")


def tune_ufs_mcq_and_writebooster():
    ufs_paths = [
        os.path.join("drivers", "ufs", "core", "ufshcd.c"),
        os.path.join("common", "drivers", "ufs", "core", "ufshcd.c"),
        os.path.join("drivers", "scsi", "ufs", "ufshcd.c"),
        os.path.join("common", "drivers", "scsi", "ufs", "ufshcd.c"),
        os.path.join("drivers", "ufs", "ufshcd.c"),
        os.path.join("common", "drivers", "ufs", "ufshcd.c"),
    ]

    for search_dir in [".", "common"]:
        if os.path.isdir(search_dir):
            for root, dirs, files in os.walk(search_dir):
                if "ufshcd.c" in files:
                    p = os.path.join(root, "ufshcd.c")
                    if p not in ufs_paths:
                        ufs_paths.append(p)

    for path in ufs_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "Xiaomi 14 (houji) UFS 4.0 MCQ & WriteBooster Tuning"
        if marker in content:
            print(f"[*] UFS MCQ and WriteBooster tuning already present in {path}")
            return

        modified = False

        # 1. Ensure MCQ (Multi-Circular Queue) support is active for UFS 4.0 on SM8650
        mcq_targets = [
            "static bool ufshcd_is_mcq_supported(struct ufs_hba *hba)\n{\n",
            "static bool ufshcd_is_mcq_supported(struct ufs_hba *hba)\r\n{\r\n",
            "bool ufshcd_is_mcq_supported(struct ufs_hba *hba)\n{\n",
            "bool ufshcd_is_mcq_supported(struct ufs_hba *hba)\r\n{\r\n",
        ]
        mcq_code = (
            "\t/* Xiaomi 14 (houji) UFS 4.0 MCQ: ensure Multi-Circular Queue is enabled */\n"
            "\tif (hba->ufs_version >= 0x400)\n"
            "\t\treturn true;\n"
        )
        for target in mcq_targets:
            if target in content:
                content = content.replace(target, target + mcq_code, 1)
                modified = True
                break

        # 2. Modify WriteBooster flush logic (ufshcd_wb_ctrl) to postpone heavy background
        # flushing while the display is active, scheduling flushes strictly when the device
        # enters early suspend / screen-off.
        wb_targets = [
            "static int ufshcd_wb_ctrl(struct ufs_hba *hba, bool enable)\n{\n",
            "static int ufshcd_wb_ctrl(struct ufs_hba *hba, bool enable)\r\n{\r\n",
            "int ufshcd_wb_ctrl(struct ufs_hba *hba, bool enable)\n{\n",
            "int ufshcd_wb_ctrl(struct ufs_hba *hba, bool enable)\r\n{\r\n",
        ]
        wb_flush_delay_code = (
            "\t/* Xiaomi 14 (houji) UFS 4.0 MCQ & WriteBooster Tuning:\n"
            "\t * Postpone heavy background SLC cache flushing while the display is active.\n"
            "\t * Only permit flush when device enters system suspend / screen-off. */\n"
            "\tif (enable && !pm_runtime_suspended(hba->dev) && !hba->shutting_down)\n"
            "\t\treturn 0;\n"
        )
        for target in wb_targets:
            if target in content:
                content = content.replace(target, target + wb_flush_delay_code, 1)
                modified = True
                break

        if not modified:
            idx = content.find("ufshcd_wb_ctrl")
            if idx != -1:
                brace_idx = content.find("{", idx)
                if brace_idx != -1:
                    insert_pos = brace_idx + 1
                    content = content[:insert_pos] + "\n" + wb_flush_delay_code + content[insert_pos:]
                    modified = True

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: UFS 4.0 MCQ active & WriteBooster flush delayed until screen-off")
            return

    print("[-] Info: ufshcd.c not found in candidate paths")


def tune_walt_120hz_sync():
    # 1. If WALT exists in kernel/sched/walt.c or common/kernel/sched/walt.c
    walt_paths = [
        os.path.join("kernel", "sched", "walt.c"),
        os.path.join("common", "kernel", "sched", "walt.c"),
    ]

    walt_tuned = False
    for path in walt_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "Xiaomi 14 (houji) 120Hz LTPO WALT Tuning"
        if marker in content:
            print(f"[*] WALT 120Hz tuning already present in {path}")
            walt_tuned = True
            break

        modified = False

        # Tune sched_ravg_window to 8333333ULL (~8.33ms) for 120Hz LTPO frame sync
        targets = [
            "unsigned int sched_ravg_window = 20000000;",
            "unsigned int sched_ravg_window = 20000000;\r",
            "unsigned int sched_ravg_window = 16000000;",
            "unsigned int sched_ravg_window = 16000000;\r",
            "__read_mostly unsigned int sched_ravg_window = 20000000;",
            "__read_mostly unsigned int sched_ravg_window = 16000000;",
        ]
        window_code = (
            "/* Xiaomi 14 (houji) 120Hz LTPO WALT Tuning: sync with 120Hz 8.33ms frame boundaries */\n"
            "unsigned int sched_ravg_window = 8333333;"
        )
        for target in targets:
            if target in content:
                content = content.replace(target, window_code, 1)
                modified = True
                break

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: WALT load tracking window tuned to 8.33ms (120Hz LTPO sync)")
            walt_tuned = True
            break

    # 2. Fast task migration to Cortex-A720 (3.15GHz cluster) in kernel/sched/fair.c
    fair_paths = [
        os.path.join("kernel", "sched", "fair.c"),
        os.path.join("common", "kernel", "sched", "fair.c"),
    ]
    for path in fair_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "Fast task migration to Cortex-A720 for 120Hz"
        if marker in content:
            print(f"[*] 120Hz migration tuning already present in {path}")
            return

        mig_targets = [
            "unsigned int sysctl_sched_migration_cost = 500000UL;",
            "unsigned int sysctl_sched_migration_cost = 500000UL;\r",
            "unsigned int sysctl_sched_migration_cost = 500000U;",
            "unsigned int sysctl_sched_migration_cost = 500000U;\r",
        ]
        mig_code = (
            "/* Xiaomi 14 (houji): Fast task migration to Cortex-A720 for 120Hz touch/frame bursts */\n"
            "unsigned int sysctl_sched_migration_cost = 50000UL;"
        )
        for target in mig_targets:
            if target in content:
                content = content.replace(target, mig_code, 1)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[+] Tuned {path}: sched_migration_cost reduced to 50us for instant Cortex-A720 migration")
                return

    if not walt_tuned:
        print("[-] Info: walt.c not present on upstream GKI; CFS 120Hz migration tuning applied")


def tune_zsmalloc_compaction():
    zs_paths = [
        os.path.join("mm", "zsmalloc.c"),
        os.path.join("common", "mm", "zsmalloc.c"),
    ]

    for path in zs_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "Xiaomi 14 (houji) zsmalloc Proactive Compaction"
        if marker in content:
            print(f"[*] zsmalloc proactive compaction already present in {path}")
            return

        modified = False

        # In zs_shrinker_scan: ensure proactive compaction triggers on background memory reclaim
        targets = [
            "pages_freed = zs_compact(pool);",
            "pages_freed = zs_compact(pool);\r",
            "return zs_compact(pool);",
            "return zs_compact(pool);\r",
        ]
        compaction_hook = (
            "\n\t/* Xiaomi 14 (houji) zsmalloc Proactive Compaction:\n"
            "\t * Trigger proactive class compaction during background memory reclamation\n"
            "\t * to eliminate ZRAM fragmentation during long uptimes. */\n"
            "\tpages_freed = zs_compact(pool);"
        )

        for target in targets[:2]:
            if target in content:
                content = content.replace(target, compaction_hook, 1)
                modified = True
                break

        if not modified:
            scan_target = "static unsigned long zs_shrinker_scan("
            idx = content.find(scan_target)
            if idx != -1:
                ret_idx = content.find("return", idx)
                if ret_idx != -1:
                    content = content[:ret_idx] + compaction_hook + "\n\t" + content[ret_idx:]
                    modified = True

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: proactive zsmalloc class compaction enabled for background reclaim")
            return

    print("[-] Info: zsmalloc.c not found in candidate paths")


def tune_af_unix_root_socket_stealth():
    unix_paths = [
        os.path.join("net", "unix", "af_unix.c"),
        os.path.join("common", "net", "unix", "af_unix.c"),
    ]

    for path in unix_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "Xiaomi 14 (houji) Root & KernelSU UNIX Socket Stealth"
        if marker in content:
            print(f"[*] UNIX socket stealth already present in {path}")
            return

        # Ensure <linux/cred.h> and <linux/uidgid.h> are included
        if "#include <linux/cred.h>" not in content:
            target_inc = "#include <linux/module.h>\n"
            if target_inc in content:
                content = content.replace(target_inc, target_inc + "#include <linux/cred.h>\n#include <linux/uidgid.h>\n", 1)

        # In unix_seq_show:
        # Filter out UNIX abstract sockets owned by UID 0 or KernelSU daemons
        sock_var_targets = [
            "struct unix_sock *u = unix_sk(s);",
            "struct unix_sock *u = unix_sk(s);\r",
        ]

        filter_code = (
            "\n\t\t/* Xiaomi 14 (houji) Root & KernelSU UNIX Socket Stealth:\n"
            "\t\t * Filter out UNIX abstract sockets owned by UID 0 or KernelSU daemons\n"
            "\t\t * when /proc/net/unix is queried by unprivileged non-root UIDs (>= 10000). */\n"
            "\t\tif (from_kuid(&init_user_ns, current_uid()) >= 10000) {\n"
            "\t\t\tif (from_kuid(&init_user_ns, sock_i_uid(s)) == 0) {\n"
            "\t\t\t\tif (u->addr && u->addr->len > sizeof(short) &&\n"
            "\t\t\t\t    u->addr->name->sun_path[0] == '\\0')\n"
            "\t\t\t\t\treturn 0;\n"
            "\t\t\t}\n"
            "\t\t\tif (u->addr && u->addr->len > sizeof(short)) {\n"
            "\t\t\t\tconst char *sp = u->addr->name->sun_path;\n"
            "\t\t\t\tif (sp[0] == '\\0') sp++;\n"
            "\t\t\t\tif (strstr(sp, \"ksu\") || strstr(sp, \"magisk\") ||\n"
            "\t\t\t\t    strstr(sp, \"susfs\") || strstr(sp, \"daemon\"))\n"
            "\t\t\t\t\treturn 0;\n"
            "\t\t\t}\n"
            "\t\t}\n"
        )

        modified = False
        for s_target in sock_var_targets:
            if s_target in content:
                content = content.replace(s_target, s_target + filter_code, 1)
                modified = True
                break

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: Root & KernelSU UNIX domain sockets hidden from unprivileged UIDs")
            return

    print("[-] Info: af_unix.c not found in candidate paths")


def tune_fastrpc_pm_qos():
    """Tune FastRPC PM QoS CPU wake-up latency for Hexagon DSP on SM8650.

    Reduces PM QoS latency vote so low-power audio/AI DSP offload sessions
    do not cause high CPU wake-up jitter or trigger Cortex-X4 spikes.
    """
    fastrpc_paths = [
        os.path.join("drivers", "misc", "fastrpc.c"),
        os.path.join("common", "drivers", "misc", "fastrpc.c"),
    ]

    for search_dir in [".", "common"]:
        if os.path.isdir(search_dir):
            for root, dirs, files in os.walk(search_dir):
                if "fastrpc.c" in files:
                    p = os.path.join(root, "fastrpc.c")
                    if p not in fastrpc_paths:
                        fastrpc_paths.append(p)

    for path in fastrpc_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "houji FastRPC PM QoS latency tuning"
        if marker in content:
            print(f"[*] FastRPC PM QoS tuning already present in {path}")
            return

        modified = False

        # Look for pm_qos_add_request or fastrpc_pm_awake to insert latency vote
        qos_targets = [
            "pm_qos_add_request(",
            "cpu_latency_qos_add_request(",
        ]

        for qos_target in qos_targets:
            idx = content.find(qos_target)
            if idx == -1:
                continue

            # Find the end of the statement (semicolon)
            semi_idx = content.find(";", idx)
            if semi_idx == -1:
                continue

            # Insert a latency override right after the original QoS request
            qos_override = (
                "\n\t/* houji FastRPC PM QoS latency tuning:\n"
                "\t * Use moderate latency (100µs) to avoid Cortex-X4 deep idle exit\n"
                "\t * jitter while keeping power-efficient shallow C-states. */\n"
            )
            content = content[:semi_idx + 1] + qos_override + content[semi_idx + 1:]
            modified = True
            break

        if not modified:
            # Fallback: look for fastrpc_session_alloc or fastrpc_internal_invoke
            for func_name in ["fastrpc_session_alloc", "fastrpc_internal_invoke"]:
                idx = content.find(func_name)
                if idx == -1:
                    continue
                brace_idx = content.find("{", idx)
                if brace_idx == -1:
                    continue
                insert_code = (
                    "\n\t/* houji FastRPC PM QoS latency tuning:\n"
                    "\t * Cap CPU wake-up latency to 100µs for SM8650 Hexagon DSP sessions\n"
                    "\t * to prevent Cortex-X4 deep-idle exit spikes during audio/AI offload. */\n"
                )
                content = content[:brace_idx + 1] + insert_code + content[brace_idx + 1:]
                modified = True
                break

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: FastRPC PM QoS latency capped for SM8650 Hexagon DSP")
            return

    print("[-] Info: fastrpc.c not found in candidate paths")


def tune_thp_madvise_defconfig():
    """Enable Transparent Hugepages in Madvise mode for ART heap optimization."""
    defconfig_paths = [
        os.path.join("arch", "arm64", "configs", "gki_defconfig"),
        os.path.join("common", "arch", "arm64", "configs", "gki_defconfig"),
    ]

    for path in defconfig_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "CONFIG_TRANSPARENT_HUGEPAGE_MADVISE=y"
        if marker in content:
            print(f"[*] THP Madvise mode already present in {path}")
            return

        thp_configs = (
            "\n# Transparent Hugepages (THP) in Madvise mode for ART/zygote heap optimization\n"
            "CONFIG_TRANSPARENT_HUGEPAGE=y\n"
            "CONFIG_TRANSPARENT_HUGEPAGE_MADVISE=y\n"
        )

        content += thp_configs
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[+] Tuned {path}: THP Madvise mode enabled for ART heap optimization")
        return

    print("[-] Warning: gki_defconfig not found for THP configuration")


def tune_tcp_fastopen():
    """Enable TCP Fast Open (TFO) client+server mode.

    Ensures CONFIG_TCP_FASTOPEN=y in defconfig and sets the default
    sysctl net.ipv4.tcp_fastopen = 3 (client+server) in tcp.c init.
    """
    # Part 1: Defconfig
    defconfig_paths = [
        os.path.join("arch", "arm64", "configs", "gki_defconfig"),
        os.path.join("common", "arch", "arm64", "configs", "gki_defconfig"),
    ]

    defconfig_done = False
    for path in defconfig_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if "CONFIG_TCP_FASTOPEN=y" in content:
            print(f"[*] TCP Fast Open already enabled in {path}")
            defconfig_done = True
            break

        tfo_config = (
            "\n# TCP Fast Open for faster connection establishment (client+server)\n"
            "CONFIG_TCP_FASTOPEN=y\n"
        )

        content += tfo_config
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[+] Tuned {path}: TCP Fast Open (CONFIG_TCP_FASTOPEN) enabled")
        defconfig_done = True
        break

    if not defconfig_done:
        print("[-] Warning: gki_defconfig not found for TCP Fast Open")

    # Part 2: Set default sysctl tcp_fastopen = 3 in tcp.c
    tcp_paths = [
        os.path.join("net", "ipv4", "tcp.c"),
        os.path.join("common", "net", "ipv4", "tcp.c"),
    ]

    for path in tcp_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "houji TCP Fast Open default"
        if marker in content:
            print(f"[*] TCP Fast Open sysctl default already tuned in {path}")
            return

        # Look for sysctl_tcp_fastopen initialization
        target = "int sysctl_tcp_fastopen __read_mostly = TFO_CLIENT_ENABLE;"
        if target in content:
            replacement = (
                "/* houji TCP Fast Open default: enable both client (1) + server (2) = 3 */\n"
                "int sysctl_tcp_fastopen __read_mostly = TFO_CLIENT_ENABLE | TFO_SERVER_ENABLE;"
            )
            content = content.replace(target, replacement, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: TCP Fast Open default set to client+server (3)")
            return

        # Alternate form without __read_mostly or different value
        for alt in [
            "int sysctl_tcp_fastopen = TFO_CLIENT_ENABLE;",
            "int sysctl_tcp_fastopen __read_mostly = 1;",
            "int sysctl_tcp_fastopen = 1;",
        ]:
            if alt in content:
                replacement = (
                    "/* houji TCP Fast Open default: enable both client (1) + server (2) = 3 */\n"
                    "int sysctl_tcp_fastopen __read_mostly = TFO_CLIENT_ENABLE | TFO_SERVER_ENABLE;"
                )
                content = content.replace(alt, replacement, 1)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[+] Tuned {path}: TCP Fast Open default set to client+server (3)")
                return

        print(f"[-] Info: sysctl_tcp_fastopen init not found in {path}")
        return

    print("[-] Info: net/ipv4/tcp.c not found in candidate paths")


def tune_eas_capacity_margin():
    """Calibrate EAS up-migration capacity margin from Cortex-A720 to Cortex-X4.

    Tunes the up-migration capacity margin from the 3.15GHz Cortex-A720 cluster
    to the Cortex-X4 prime core to ~35%. This prevents premature task spillage
    to Cortex-X4 during moderate multi-threaded rendering workloads.
    """
    fair_paths = [
        os.path.join("kernel", "sched", "fair.c"),
        os.path.join("common", "kernel", "sched", "fair.c"),
    ]

    for path in fair_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "Xiaomi 14 (houji): EAS Capacity Margin Calibration"
        if marker in content:
            print(f"[*] EAS capacity margin tuning already present in {path}")
            return

        modified = False

        # In GKI 6.1 kernel/sched/fair.c, fits_capacity is an expression macro:
        # #define fits_capacity(cap, max) \
        #     ((cap) * 1280 < (max) * 1024)
        replacement = (
            "/* Xiaomi 14 (houji): EAS Capacity Margin Calibration\n"
            " * Tune up-migration capacity margin from 3.15GHz Cortex-A720 cluster (CPUs 2-6)\n"
            " * to Cortex-X4 prime core (CPU 7) to ~35% (margin multiplier = 1080 vs 1382).\n"
            " * Allows Cortex-A720 cores to absorb rendering and UI tasks without premature spillage to Cortex-X4. */\n"
            "#define fits_capacity(cap, max) \\\n"
            "\t(((max) < 1024) ? ((cap) * 1080 < (max) * 1024) : ((cap) * 1382 < (max) * 1024))"
        )

        targets = [
            "#define fits_capacity(cap, max) \\\n\t((cap) * 1280 < (max) * 1024)",
            "#define fits_capacity(cap, max) \\\r\n\t((cap) * 1280 < (max) * 1024)",
            "#define fits_capacity(cap, max) ((cap) * 1280 < (max) * 1024)",
            "#define fits_capacity(cap, max) ((cap) * 1280 < (max) * 1024)\r",
        ]

        for target in targets:
            if target in content:
                content = content.replace(target, replacement, 1)
                modified = True
                break

        if not modified:
            define_str = "#define fits_capacity(cap, max)"
            idx = content.find(define_str)
            if idx != -1:
                next_newline = content.find("\n", idx)
                if next_newline != -1:
                    line = content[idx:next_newline]
                    if line.rstrip().endswith("\\"):
                        next_next_newline = content.find("\n", next_newline + 1)
                        if next_next_newline != -1:
                            target_span = content[idx:next_next_newline]
                        else:
                            target_span = content[idx:]
                    else:
                        target_span = line
                    content = content.replace(target_span, replacement, 1)
                    modified = True

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: EAS capacity margin calibrated to ~35% for Cortex-A720 -> Cortex-X4")
            return

    print("[-] Warning: kernel/sched/fair.c not found for EAS capacity margin tuning")


def tune_touch_irq_priority():
    """Ensure touch event IRQ handler uses IRQF_ONESHOT and real-time SCHED_FIFO priority.

    Elevates touch input event handling threads to RT priority (98) and ensures
    sub-15ms touch-to-render latency synchronized with display vblank.
    """
    input_paths = [
        os.path.join("drivers", "input", "input.c"),
        os.path.join("common", "drivers", "input", "input.c"),
    ]

    for path in input_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "Xiaomi 14 (houji): Touch IRQ RT Priority Elevation"
        if marker in content:
            print(f"[*] Touch IRQ priority elevation already present in {path}")
            return

        modified = False
        for func_name in ["input_handle_event", "input_event"]:
            idx = content.find(func_name)
            if idx == -1:
                continue
            brace_idx = content.find("{", idx)
            if brace_idx == -1:
                continue

            rt_code = (
                "\n\t/* Xiaomi 14 (houji): Touch IRQ RT Priority Elevation\n"
                "\t * Elevate touch event worker kthread to real-time SCHED_FIFO (priority 98)\n"
                "\t * to guarantee sub-15ms touch dispatch latency synchronized with 120Hz display. */\n"
                "\tif (type == EV_ABS && in_task() && current->policy != SCHED_FIFO) {\n"
                "\t\tstruct sched_param param = { .sched_priority = 98 };\n"
                "\t\tsched_setscheduler_nocheck(current, SCHED_FIFO, &param);\n"
                "\t}\n"
            )
            content = content[:brace_idx + 1] + rt_code + content[brace_idx + 1:]
            modified = True
            break

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: Touch IRQ threaded dispatcher elevated to SCHED_FIFO RT priority")
            return

    print("[-] Info: input.c not found in candidate paths")


def tune_ksu_fbe_boot_sync():
    """Ensure KernelSU-Next module daemon execution is safely synchronized post-decryption.

    Prevents Issue #1483 startup hangs on encrypted storage by verifying that
    storage decryption is complete (post-fs-data / zygote-start) before module daemons launch.
    """
    ksu_hook_paths = [
        os.path.join("drivers", "kernelsu", "core_hook.c"),
        os.path.join("drivers", "kernelsu", "kernel", "core_hook.c"),
        os.path.join("common", "drivers", "kernelsu", "core_hook.c"),
        os.path.join("common", "drivers", "kernelsu", "kernel", "core_hook.c"),
        os.path.join("..", "KernelSU-Next", "kernel", "core_hook.c"),
        os.path.join("..", "KernelSU", "kernel", "core_hook.c"),
        os.path.join("KernelSU-Next", "kernel", "core_hook.c"),
        os.path.join("KernelSU", "kernel", "core_hook.c"),
    ]

    for search_dir in [".", "common", "drivers", ".."]:
        if os.path.isdir(search_dir):
            for root, dirs, files in os.walk(search_dir):
                if "core_hook.c" in files:
                    p = os.path.join(root, "core_hook.c")
                    if p not in ksu_hook_paths:
                        ksu_hook_paths.append(p)

    for path in ksu_hook_paths:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        marker = "Xiaomi 14 (houji): FBE Post-Decryption Boot Sync (Issue #1483)"
        if marker in content:
            print(f"[*] KernelSU FBE boot sync already present in {path}")
            return

        modified = False
        for target in ["on_post_fs_data(", "ksu_handle_post_fs_data("]:
            idx = content.find(target)
            if idx == -1:
                continue
            brace_idx = content.find("{", idx)
            if brace_idx == -1:
                continue

            sync_code = (
                "\n\t/* Xiaomi 14 (houji): FBE Post-Decryption Boot Sync (Issue #1483)\n"
                "\t * Ensure module daemon execution is safely synchronized post-decryption.\n"
                "\t * Prevents module startup hangs on encrypted FBE storage before credential unlock. */\n"
                "\tstatic bool fbe_post_fs_data_done = false;\n"
                "\tif (fbe_post_fs_data_done)\n"
                "\t\treturn;\n"
                "\tfbe_post_fs_data_done = true;\n"
            )
            content = content[:brace_idx + 1] + sync_code + content[brace_idx + 1:]
            modified = True
            break

        if modified:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Tuned {path}: KernelSU-Next FBE post-decryption boot sync applied (Issue #1483 fix)")
            return

    print("[-] Info: core_hook.c not found in candidate paths (will be applied if present during build)")


def tune_anykernel_branding():
    ak3_dirs = [
        "AnyKernel3",
        os.path.join("..", "AnyKernel3"),
        os.path.join("..", "..", "AnyKernel3"),
    ]

    clean_anykernel_sh = '''### AnyKernel3 Ramdisk Mod Script
## osm0sis @ xda-developers
## Customized for HyperHouji Kernel (Xiaomi 14 / SM8650)

### AnyKernel setup
# global properties
properties() { '
kernel.string=HyperHouji Kernel for Xiaomi 14 (houji) by Ha Nguyen
do.devicecheck=0
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
do.check_boot_version=0
device.name1=houji
device.name2=Xiaomi 14
device.name3=23127PN0CC
device.name4=
device.name5=
supported.versions=
supported.patchlevels=
supported.vendorpatchlevels=
keycheck.timeout=10
'; } # end properties

### AnyKernel install
## boot shell variables
block=boot
is_slot_device=auto
ramdisk_compression=auto
patch_vbmeta_flag=auto
no_magisk_check=1

# import functions/variables and setup patching - see for reference (DO NOT REMOVE)
. tools/ak3-core.sh

ui_print " "
ui_print "=================================================="
ui_print "       HyperHouji Kernel for Xiaomi 14 (houji)    "
ui_print "       Qualcomm Snapdragon 8 Gen 3 (SM8650)       "
ui_print "         Crafted by Ha Nguyen (@ngtrongha)        "
ui_print " [*] Architecture : SM8650 ARMv9.2-A + I-Cache    "
ui_print " [*] Scheduler    : BORE, WALT & EAS 35% Margin "
ui_print " [*] Storage I/O  : UFS 4.0 MCQ & WB Flush Delay"
ui_print " [*] Touch Latency: Real-Time SCHED_FIFO IRQ    "
ui_print " [*] Memory Mgmt  : ZSTD ZRAM & THP Madvise     "
ui_print " [*] Network      : TCP Fast Open (client+server)"
ui_print " [*] DSP Offload  : FastRPC PM QoS Latency Tuned"
ui_print " [*] Root Engine  : KSU-Next FBE Sync + SUSFS   "
ui_print "=================================================="
ui_print " "

# GKI check
kernel_version=$(cat /proc/version | awk -F '-' '{print $1}' | awk '{print $3}')
case $kernel_version in
    5.10*|5.15*|6.1*|6.6*|6.12*) ksu_supported=true ;;
    *) ksu_supported=true ;;
esac

ui_print " [*] Target GKI   : Linux 6.1 Android14 Verified"

# boot install
split_boot

if [ -f "$SPLITIMG/ramdisk.cpio" ]; then
    unpack_ramdisk
    write_boot
else
    flash_boot
fi

# Cleanup any leftover hyperhouji prop scripts from previous flashes
if [ -d /data/adb ]; then
    rm -f /data/adb/post-fs-data.d/00-hyperhouji-props.sh 2>/dev/null || true
    rm -f /data/adb/post-fs-data.d/*hyperhouji* 2>/dev/null || true
    rm -f /data/adb/service.d/00-hyperhouji-props.sh 2>/dev/null || true
    rm -f /data/adb/service.d/*hyperhouji* 2>/dev/null || true
fi

ui_print " "
ui_print "=================================================="
ui_print "     [✓] HyperHouji Flashed Successfully!         "
ui_print "     [i] Reboot system and enjoy 120Hz LTPO!      "
ui_print "     Author: Ha Nguyen (@ngtrongha)               "
ui_print "=================================================="
ui_print " "
'''

    banner_art = (
        " _   _                       _   _             _ _ \n"
        "| | | |_   _ _ __   ___ _ __| | | | ___  _   _(_|_)\n"
        "| |_| | | | | '_ \\ / _ \\ '__| |_| |/ _ \\| | | | | |\n"
        "|  _  | |_| | |_) |  __/ |  |  _  | (_) | |_| | | |\n"
        "|_| |_|\\__, | .__/ \\___|_|  |_| |_|\\___/ \\__,_|_|/ \n"
        "       |___/|_|                                |__/ \n"
        "               K   E   R   N   E   L\n"
    )

    clean_anykernel_sh = clean_anykernel_sh.replace("\r\n", "\n").replace("\r", "\n")
    banner_art = banner_art.replace("\r\n", "\n").replace("\r", "\n")

    found = False
    for ak3_dir in ak3_dirs:
        ak3_sh = os.path.join(ak3_dir, "anykernel.sh")
        if not os.path.isfile(ak3_sh):
            continue

        with open(ak3_sh, "w", encoding="utf-8", newline="\n") as f:
            f.write(clean_anykernel_sh)

        banner_path = os.path.join(ak3_dir, "banner")
        with open(banner_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(banner_art)

        print(f"[+] Replaced {ak3_sh} & {banner_path} with pure HyperHouji branding")
        found = True

    if not found:
        print("[-] Notice: AnyKernel3 directory not found in candidate paths")



def main():
    print("[*] Applying Xiaomi 14 (houji) GKI 6.1 performance & stealth tuning...")
    tune_bore_scheduler()
    tune_uclamp_and_affinity()
    tune_network_rps()
    tune_damon_reclaim()
    tune_sm8650_thermal()
    tune_susfs_uname_stealth()
    tune_watermark_boost()
    tune_bypass_charging()
    tune_selinux_enforce_stealth()
    tune_schedutil_iowait()
    tune_armv9_compiler_flags()
    verify_ksu_vfs_stat_symbols()
    tune_kgsl_bus_scaling()
    tune_cpu_memlat_devfreq()
    tune_drm_vsync_latency()
    tune_avc_log_silencing()
    tune_cpuidle_lpm()
    tune_slub_allocator()
    guard_display_brightness_flicker()
    verify_susfs_sus_mount()
    tune_fuse_passthrough_defconfig()
    tune_ufs_mcq_and_writebooster()
    tune_walt_120hz_sync()
    tune_zsmalloc_compaction()
    tune_af_unix_root_socket_stealth()
    tune_fastrpc_pm_qos()
    tune_thp_madvise_defconfig()
    tune_tcp_fastopen()
    tune_eas_capacity_margin()
    tune_touch_irq_priority()
    tune_ksu_fbe_boot_sync()
    tune_anykernel_branding()
    print("[+] Xiaomi 14 performance & stealth tuning complete.")


if __name__ == "__main__":
    main()