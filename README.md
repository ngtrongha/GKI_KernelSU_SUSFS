<div align="center">

# HNHouji Kernel — Xiaomi 14 (houji) & Android GKI 2.0

Hardened, hardware-safe Android Generic Kernel Image (GKI 2.0) built on **Google ACK 6.1 LTS**, engineered specifically for **Xiaomi 14 (`houji` / SM8650 `pineapple`)** running HyperOS, with full generic GKI compatibility.

[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Kernel Base](https://img.shields.io/badge/Google%20ACK-6.1%20LTS-brightgreen.svg)](https://android.googlesource.com/kernel/common/+/refs/heads/android14-6.1)
[![KernelSU-Next](https://img.shields.io/badge/Root-KernelSU--Next-orange.svg)](https://github.com/KernelSU-Next/KernelSU-Next)
[![SUSFS](https://img.shields.io/badge/Hide-SUSFS%20v2.3.0-purple.svg)](https://gitlab.com/simonpunk/susfs4ksu)
[![Device Verified](https://img.shields.io/badge/Xiaomi%2014-Tested%20%26%20Verified%20(r8)-success.svg)](https://github.com/ngtrongha/GKI_KernelSU_SUSFS/releases/tag/r8)

</div>

> [!CAUTION]
> Modifying your kernel carries inherent risks. While HNHouji is engineered with strict hardware shields and verified against device baselines, you assume all risk by flashing. Always backup your `boot` partition before flashing.

---

## Highlights: Xiaomi 14 Hardware Shielding

Standard upstream GKI kernels often suffer from black screens, screen flickering, or bootloops on Xiaomi 14 due to proprietary vendor module expectations. HNHouji implements targeted hardware shielding:

- 🛡️ **Zero Black Screen Guarantee**: Surgically pins Display DRM (`drivers/gpu/drm/`, `include/drm/`), Backlight (`drivers/video/backlight/`, `include/linux/backlight.h`), and SPMI (`drivers/spmi/`) to stock 6.1.138 baseline (`0c3d559bcd85`). Matches Xiaomi's prebuilt vendor display modules (`msm_drm.ko`, `mi_disp.ko`) with 100% binary ABI compatibility.
- 👁️ **LTPO & Brightness Flicker Elimination**: Fixes VBlank and MIPI-DSI `0x51` brightness modulation timing shifts introduced in post-6.1.138 upstream ACK, providing butter-smooth 1–120 Hz LTPO refresh and stable low-light brightness.
- 💾 **F2FS `/data` Mount Integrity**: Aligns struct layout in `fs/f2fs/f2fs.h` so Xiaomi's vendor memory hooks (`mi_ext_lru.ko`, `mi_memory.ko`) mount encrypted `/data` partitions cleanly without panics.
- 🔔 **Xiaomi 14 Notification Keeper**: Bundled AnyKernel3 auto-installer deploys `houji-notification-helper.sh` into `/data/adb/service.d/` to exempt Google Play Services from aggressive Xiaomi Greezer freezing and keep FCM TCP 5228 push notifications alive.
- ⚡ **Pure Google ACK Stability**: Built strictly upon official Google Android Common Kernel `android14-6.1` LTS sources without unsafe memory reclaim hacks or PSI dampening that could lead to deadlocks.

---

## Core Features

### Root & Detection Evasion
- **KernelSU-Next**: Latest dev-susfs branch with full root isolation and app profile management.
- **SUSFS v2.3.0**: Advanced kernel-level root hiding:
  - Mount namespace isolation (KSU / Magisk / APatch invisible to detection apps).
  - Ptrace leak protection and Unicode path obfuscation.
- **NoMount / Mountify**: Full compatibility with modern systemless metamodules.

### Security & Hardware Protection
- **Baseband Guard (BBG)**: Prevents accidental overwriting or corruption of critical radio, modem, and EFS NVRAM partitions.
- **Weak Fake SELinux State**: Zero link-time symbol conflicts with root managers.

### Networking & Performance
- **BBRv3 TCP**: Google BBR v3 congestion control for lower latency and improved throughput over cellular/Wi-Fi.
- **WireGuard & IPSet**: In-kernel WireGuard VPN and fast packet filtering.
- **NTSync**: High-performance Windows NT synchronization primitives for Wine, Proton, and Box64/FEX gaming.
- **Modern Observability**: BTF, eBPF, and FUSE-BPF enabled out of the box.
- **DroidSpaces-OSS**: Full kernel container runtime support.

---

## Installation Guide

### Recommended: Kernel Flasher (Rooted)
1. Download the latest `AnyKernel3.zip` (e.g., `6.1.177-android14-lts-KernelSU-Next-AnyKernel3.zip`) from [Releases](https://github.com/ngtrongha/GKI_KernelSU_SUSFS/releases).
2. Open **[Kernel Flasher](docs/kernelflasher.md)** on your device.
3. Backup your existing `boot` partition (or have a stock `boot.img` handy).
4. Select the downloaded AnyKernel3 zip and flash.
5. Reboot.

### Alternative: Custom Recovery (TWRP / OrangeFox)
1. Boot into TWRP or OrangeFox recovery.
2. Flash the `AnyKernel3.zip` directly.
3. Reboot to system.

For step-by-step guides, see:
- [Installation Overview](docs/installation.md)
- [Kernel Flasher Guide](docs/kernelflasher.md)
- [Magiskboot Manual Patching](docs/magiskboot.md)
- [Post-Install Verification](docs/post-install.md)

---

## Verified Baseline

- **Hardware**: Xiaomi 14 (`houji`, Snapdragon 8 Gen 3 / SM8650 `pineapple`).
- **Firmware Tested**: HyperOS `OS3.0.307.0.WNCCNXM` (patch level 2026-08-01).
- **Verified Working Milestone**: [Release 8 (r8)](https://github.com/ngtrongha/GKI_KernelSU_SUSFS/releases/tag/r8) — 0% black screen, 0% LTPO flicker, clean F2FS mount.
- **Default Pipeline**: Google ACK 6.1 LTS branch (`android14-6.1`) with verified DRM/SPMI pin.

---

## Build Your Own Kernel

You can trigger a custom build directly in GitHub Actions:
1. Navigate to the **Actions** tab in this repository.
2. Select **Build Kernel (CI)**.
3. Click **Run workflow** with your preferred inputs:
   - **Kernel Version**: `6.1`
   - **OS Patch Level**: `lts` (Google ACK LTS — Recommended)
   - **Root Flavor**: `KernelSU-Next`
   - **Feature Set**: `All` (or custom subset)
4. Download the generated `AnyKernel3.zip` from the workflow summary or releases.

For custom forks and full configuration options, refer to [Build From Fork](docs/build-from-fork.md).

---

## Special Thanks & Credits

This project stands on the shoulders of incredible open-source developers:

- **Google Android Common Kernel (ACK)** — Upstream LTS foundation
- **KernelSU** — [tiann](https://github.com/tiann/KernelSU)
- **KernelSU-Next** — [rifsxd](https://github.com/KernelSU-Next/KernelSU-Next) & [pershoot](https://github.com/pershoot/KernelSU-Next)
- **SUSFS** — [simonpunk](https://gitlab.com/simonpunk/susfs4ksu) & [sidex15](https://github.com/sidex15)
- **NoMount** — [maxsteeel](https://github.com/maxsteeel/nomount)
- **Baseband Guard** — [vc-teahouse](https://github.com/vc-teahouse/Baseband-guard)
- **AnyKernel3** — [osm0sis](https://github.com/osm0sis/AnyKernel3) & [WildKernels](https://github.com/WildKernels)
- **DroidSpaces-OSS** — [ravindu644](https://github.com/ravindu644/Droidspaces-OSS)
- **NTSync & BBRv3** — Upstream Linux Kernel contributors
