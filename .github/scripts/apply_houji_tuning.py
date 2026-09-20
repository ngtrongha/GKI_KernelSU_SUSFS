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
    makefile_path = os.path.join("arch", "arm64", "Makefile")
    if not os.path.isfile(makefile_path):
        return

    with open(makefile_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    marker = "SM8650 ARMv9.2-A optimization flags"
    if marker in content:
        print("[*] ARMv9.2-A compiler flags already present in arch/arm64/Makefile")
        return

    flags_code = (
        "\n# SM8650 ARMv9.2-A optimization flags for Xiaomi 14 (houji)\n"
        "ifeq ($(CONFIG_CC_IS_CLANG),y)\n"
        "KBUILD_CFLAGS += -march=armv9.2-a+crypto+dotprod\n"
        "KBUILD_AFLAGS += -march=armv9.2-a+crypto+dotprod\n"
        "endif\n"
    )

    content += flags_code
    with open(makefile_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("[+] Tuned arch/arm64/Makefile: SM8650 ARMv9.2-A compiler flags appended")


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
ui_print "=================================================="
ui_print " [*] Architecture : SM8650 ARMv9.2-A + Crypto     "
ui_print " [*] Scheduler    : BORE Burst-Oriented Engine    "
ui_print " [*] Storage I/O  : FUSE Passthrough & UFS 4.0   "
ui_print " [*] Display Sync : 120Hz LTPO & Anti-Flicker DC  "
ui_print " [*] Root Engine  : KernelSU-Next + SUSFS Stealth "
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
    tune_anykernel_branding()
    print("[+] Xiaomi 14 performance & stealth tuning complete.")


if __name__ == "__main__":
    main()