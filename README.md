<div align="center">

```text
================================================
   _  _                     _  _             _ _ 
  | || |_  _ _ __  ___ _ _ | || |___ _  _ _ (_) |
  | __ | || | '_ \/ -_) '_|| __ / _ \ || | || | |
  |_||_|\_, | .__/\___|_|  |_||_\___/\_,_|\_,_|_|
        |__/|_|                                  
     HyperHouji Performance Kernel for Xiaomi 14  
================================================
```

# HyperHouji Kernel (GKI 6.1 LTS)

**Next-Generation High-Performance & Stealth GKI Kernel for Xiaomi 14 (`houji` / SM8650)**

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Device: Xiaomi 14 (houji)](https://img.shields.io/badge/Device-Xiaomi%2014%20(houji)-orange.svg)](https://www.mi.com/)
[![SoC: Snapdragon 8 Gen 3](https://img.shields.io/badge/SoC-Snapdragon%208%20Gen%203%20(SM8650)-red.svg)](https://www.qualcomm.com/products/mobile/snapdragon/smartphones/snapdragon-8-series-mobile-platforms/snapdragon-8-gen-3-mobile-platform)
[![Kernel: GKI 6.1 LTS](https://img.shields.io/badge/Kernel-GKI%206.1%20LTS-brightgreen.svg)](https://android.googlesource.com/kernel/common/)
[![Root: KernelSU-Next](https://img.shields.io/badge/Root-KernelSU--Next-darkgreen.svg)](https://github.com/KernelSU-Next/KernelSU-Next)
[![Stealth: SUSFS v1.5.x](https://img.shields.io/badge/Stealth-SUSFS%20v1.5.x-purple.svg)](https://gitlab.com/simonpunk/susfs4ksu)
[![Toolchain: Clang ThinLTO + ARMv9.2-A](https://img.shields.io/badge/Compiler-ThinLTO%20ARMv9.2--A-blueviolet.svg)](https://llvm.org/)

**Maintained with ❤️ by [Ha Nguyen (@ngtrongha)](https://github.com/ngtrongha)**  
*Based on upstream [WildKernels GKI](https://github.com/WildKernels/GKI_KernelSU_SUSFS) with dedicated architectural enhancements for SM8650.*

---

</div>

> [!CAUTION]
> **DISCLAIMER & WARRANTY**: Flashing a custom kernel modifies core operating system components. While **HyperHouji** is rigorously tested on Xiaomi 14 (`houji`), you flash at your own risk. Always maintain a full backup of your `boot`, `init_boot`, and userdata partitions before proceeding.

---

## 📖 Overview

**HyperHouji** is an enterprise-grade, high-performance Android Common Kernel (GKI 6.1 LTS) specifically engineered and tuned for the **Xiaomi 14** (`houji`), powered by Qualcomm's **Snapdragon 8 Gen 3 (SM8650)** platform.

It combines cutting-edge scheduler enhancements (Zero-KMI BORE Engine), custom memory and storage pipelines (FUSE Passthrough, ZSTD Multi-Comp, F2FS UFS 4.0 tuning), hardware display flickering guards, and state-of-the-art stealth security features (KernelSU-Next, SUSFS v1.5.x with `SUS_MOUNT`, dynamic `sys_newuname` & `/proc/version` spoofing) to provide an uncompromising, butter-smooth 120Hz LTPO user experience while bypassing 100% of banking and enterprise root detection mechanisms.

---

## ⚡ Key Highlights & Architecture

### 1. 🎯 Zero-KMI BORE Burst Scheduler (120Hz EEVDF Optimization)
- **Fluid UI Prioritization**: Real-time burst-score tracking in `kernel/sched/fair.c`. Short interactive tasks (SurfaceFlinger, RenderThread, input pipelines < 10ms) receive zero `vruntime` penalty for instant frame delivery.
- **Batch Workload Deprioritization**: Heavy background CPU-hogs are penalized dynamically (`(burst_exec - 10ms) >> 22`), preventing micro-stutters.
- **Zero KMI Breakage**: Engineered without altering `struct task_struct` or `struct sched_entity` byte offsets—**100% immune to module mismatch bootloops**.

### 2. 🛡️ SM8650 Cortex-X4 Prime Core Protection & Thermal Guard
- **uclamp Task Affinity Policy**: Background and low-priority tasks (`nice >= 10` or `uclamp.max <= 400`) are strictly masked out from **CPU 7 (Cortex-X4 3.3GHz)**.
- **Schedutil iowait Dampening**: Eliminates unnecessary frequency spikes to maximum clock speeds caused by non-blocking UFS 4.0 flash I/O interrupts.
- **CPUIdle Low-Power Mode (LPM)**: Dynamically shortens target residency by 25% when system load is low (< 5%), guiding Cortex-X4 and A720 into Power Collapse (PC) faster to minimize idle battery drain.
- **KGSL Interconnect Scaling**: Custom GPU bus scaling for Adreno 750 to stop 2D composite frames from voting for peak LPDDR5X memory frequency.

### 3. 🖥️ Display & Panel Protection (TCL C8 OLED Anti-Flickering)
- **Anti-Flicker DC-Dimming Guard**: Resolves **WildKernels Issue #283** on Xiaomi 14's CSOT TCL C8 120Hz LTPO display. Lọc bỏ các lệnh cập nhật backlight trùng lặp, triệt tiêu hiện tượng nhấp nháy màn hình (breathing backlight) ở độ sáng thấp/vừa.
- **VSync Fence Latency Reduction**: Streamlined DRM fence signaling between SurfaceFlinger and display hardware.

### 4. 🚀 Storage & Memory Acceleration
- **FUSE Passthrough Engine**: Direct zero-copy VFS passthrough enabled for Android 14/15 `MediaProvider`, dramatically cutting context switches for gallery loading, media scanning, and high-speed I/O.
- **ZRAM ZSTD Multi-Compression**: High-throughput ZSTD compression by default with multi-stream compression enabled (`CONFIG_ZRAM_MULTI_COMP=y`).
- **Low-Latency Swap-In**: `page_cluster = 0` for 4KB single-page reads from ZRAM, slashing swap-in latency by ~30%.
- **UFS 4.0 Flash Tuning**: Elevated `hot_data_age_threshold` (2GB) and `warm_data_age_threshold` (20GB) tuned for high-bandwidth UFS 4.0 storage.
- **SLUB Allocator Optimization**: Tuned `cpu_partial` ladder (4, 12, 26, 60) in `mm/slub.c` for SM8650's 1+5+2 tri-cluster CPU topology, eliminating cross-cluster spinlock contention.

### 5. 🥷 Military-Grade Root Stealth & Detection Evasion
- **KernelSU-Next + SUSFS v1.5.x**: Next-generation kernel-level root solution paired with SUSFS file system interception.
- **Dynamic Uname & Version Spoofing**: Automatically purges custom identifiers (`-HyperHouji`, `-Wild`, `-Kow`, `-Suki`) from both `fs/proc/version.c` (`version_proc_show`) and `kernel/sys.c` (`sys_newuname`). Unprivileged apps only see clean official Google GKI strings.
- **`CONFIG_KSU_SUSFS_SUS_MOUNT=y`**: Complete stealth concealment for all KSU module and overlay mounts in `/proc/self/mountinfo` and `/proc/self/mountstats`.
- **Kallsyms & AVC Silencing**: Strips all `ksu_*` and `susfs_*` symbols from `/proc/kallsyms` and suppresses SELinux AVC denial logs to evade behavioral heuristics.

---

## 📋 Feature Matrix

| Subsystem / Area | Feature | Status | Implementation Details |
| :--- | :--- | :---: | :--- |
| **CPU Scheduling** | Zero-KMI BORE Burst Engine | ✅ Active | Dynamic burst-score tracking for 120Hz EEVDF UI frame delivery |
| **Core Isolation** | Cortex-X4 Prime Core Protection | ✅ Active | `uclamp.max = 400` cap and CPU 7 exclusion for background tasks |
| **CPU Governors** | Schedutil iowait Dampening | ✅ Active | Suppresses artificial frequency spikes triggered by UFS 4.0 flash I/O |
| **Power & Idle** | CPUIdle Low-Power Mode (LPM) | ✅ Active | 25% lower target residency at low load (< 5%) for faster Power Collapse |
| **GPU & Bus** | KGSL Interconnect Bus Scaling | ✅ Active | Tuned DDR bus table preventing 2D rendering from requesting peak freq |
| **Display** | OLED DC-Dimming Anti-Flickering | ✅ Active | Suppresses redundant backlight updates for TCL C8 1.5K 120Hz LTPO |
| **Display** | DRM VSync Latency Reduction | ✅ Active | Streamlines fence signaling between SurfaceFlinger and display hardware |
| **Storage** | FUSE Passthrough Engine | ✅ Active | Zero-copy VFS passthrough for Android 14/15 MediaProvider storage daemon |
| **Storage** | F2FS UFS 4.0 Flash Tuning | ✅ Active | Elevated data age thresholds (2GB hot / 20GB warm) for UFS 4.0 storage |
| **Memory** | ZRAM ZSTD Multi-Compression | ✅ Active | Native ZSTD compression default with concurrent multi-comp streams |
| **Memory** | Low-Latency 4KB Swap-In | ✅ Active | `page_cluster = 0` for direct single-page reads from ZRAM swap |
| **Memory** | SLUB Tri-Cluster Optimization | ✅ Active | Tuned `cpu_partial` ladder (4, 12, 26, 60) for 1+5+2 tri-cluster layout |
| **Networking** | BBRv3 + FQ / RPS Steering | ✅ Active | Advanced packet pacing + softirq steering to Little cores (CPUs 0-1) |
| **Root Security** | KernelSU-Next / ReSukiSU | ✅ Active | Next-generation kernel-level root privilege management |
| **Root Stealth** | SUSFS v1.5.x with SUS_MOUNT | ✅ Active | Conceals all KSU/overlay mounts from `/proc/self/mountinfo` & `mountstats` |
| **Anti-Detection** | Dynamic Uname & Version Spoofing | ✅ Active | Automatically purges `-HyperHouji` from `/proc/version` & `sys_newuname` |
| **Anti-Detection** | AVC Silencing & Symbol Hiding | ✅ Active | Strips `ksu_*`/`susfs_*` from `/proc/kallsyms` and silences audit denial logs |
| **Toolchain** | Clang ThinLTO + ARMv9.2-A | ✅ Active | `-march=armv9.2-a+crypto+dotprod` targeting Snapdragon 8 Gen 3 |
| **Flashing UI** | AnyKernel3 HyperHouji Banner | ✅ Active | Custom ASCII art banner, device verification, and live feature matrix |

---

## 📲 Installation

### Prerequisites
- Unlocked bootloader on **Xiaomi 14 (`houji`)**.
- A custom recovery (**TWRP** / **OrangeFox**) OR **Kernel Flasher** app (recommended).
- Stock or custom Android 14 / Android 15 ROM running GKI 6.1 LTS.

### Method 1: Flash via Kernel Flasher / Recovery (Recommended)
1. Download the latest `[HyperHouji]-KernelSU-Next-SUSFS-...-houji.zip` from [Releases](../../releases) or [Actions Artifacts](../../actions).
2. Open **Kernel Flasher** (or reboot into TWRP / OrangeFox Recovery).
3. Select the zip file and flash.
4. Enjoy the custom HyperHouji flashing screen with hardware validation:
   ```text
   ================================================
      _  _                     _  _             _ _ 
     | || |_  _ _ __  ___ _ _ | || |___ _  _ _ (_) |
     | __ | || | '_ \/ -_) '_|| __ / _ \ || | || | |
     |_||_|\_, | .__/\___|_|  |_||_\___/\_,_|\_,_|_|
           |__/|_|                                  
        HyperHouji Performance Kernel for Xiaomi 14  
   ================================================
   ```
5. Reboot system.

### Method 2: Flash via Fastboot
If you prefer flashing `boot.img` directly:
```bash
# Reboot device to bootloader
adb reboot bootloader

# Flash boot image to current slot
fastboot flash boot boot.img

# Reboot device
fastboot reboot
```

---

## 🛠️ Building with GitHub Actions

You can build your own customized **HyperHouji** kernel in the cloud for free using GitHub Actions.

1. **Fork this repository**: `https://github.com/ngtrongha/GKI_KernelSU_SUSFS`
2. Go to the **Actions** tab in your fork.
3. Select **Build Kernels** (`main.yml`) on the left sidebar.
4. Click **Run workflow** and choose branch `feature/xiaomi14-houji-tuning`.
5. Configure your desired parameters:

| Input Parameter | Recommended Value | Description |
| :--- | :--- | :--- |
| `kernel_build_version` | `6.1.x-android14` | Android GKI 6.1 LTS kernel tree |
| `os_patch_level` | `lts` | Use latest LTS kernel upstream sources |
| `root_flavor` | `KernelSU-Next` | Recommended root provider |
| `brand_name` | `HyperHouji` | Kernel identifier (auto-cleansed for banking stealth) |
| `lto_mode` | `thin` | LLVM ThinLTO for peak execution speed & lower build time |
| `arm_tune` | `armv9.2-a` | Optimized instructions for Cortex-X4 / A720 / A520 |
| `use_perf` | `true` | Apply HyperHouji & performance tuning patches |

6. Once the build completes (~15 minutes), download the flashable AnyKernel3 zip and APK manager directly from the **Artifacts** section.

---

## 🤝 Upstream & Credits

HyperHouji is built on top of the incredible open-source work of the Android kernel community:

- **Base GKI CI & Patch Framework**: [WildKernels (@TheWildJames)](https://github.com/WildKernels/GKI_KernelSU_SUSFS)
- **SUSFS**: [simonpunk](https://gitlab.com/simonpunk/susfs4ksu)
- **KernelSU-Next**: [rifsxd](https://github.com/KernelSU-Next/KernelSU-Next) & [pershoot](https://github.com/pershoot/KernelSU-Next)
- **ReSukiSU**: [ReSukiSU Team](https://github.com/ReSukiSU/ReSukiSU)
- **Original KernelSU**: [tiann](https://github.com/tiann/KernelSU)
- **AnyKernel3**: [osm0sis](https://github.com/osm0sis/AnyKernel3)
- **NoMount**: [maxsteeel](https://github.com/maxsteeel/nomount)
- **Baseband Guard (BBG)**: [vc-teahouse](https://github.com/vc-teahouse/Baseband-guard)
- **Linux Kernel & Android Open Source Project (AOSP)**: [Google](https://android.googlesource.com/kernel/common/)

---

## 📜 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)** - see the [LICENSE](LICENSE) file for details.
All kernel code follows the upstream Linux Kernel GPL-2.0 / GPL-3.0 requirements.
