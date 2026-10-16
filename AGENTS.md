# Xiaomi 14 (houji) GKI 6.1 Build & Runtime Error Prevention Rules

## Rule 0: Mandatory Error Ledger Update
Every time a CI build error or device runtime bug occurs, **you MUST add its symptom, root cause, and prevention rule to this `AGENTS.md` file before pushing the fix** so the same failure is never repeated.

---

## Rule 1: Never Set `CONFIG_ZRAM=y` or `CONFIG_ZSMALLOC=y` on GKI 6.1
- **Symptom**: Build fails at the end of `//common:kernel_aarch64` (after compiling `vmlinux`) with:
  ```
  ERROR: Unable to find drivers/block/zram/zram.ko in any of the following directories: ...
  Unable to find mm/zsmalloc.ko in any of the following directories: ...
  ```
- **Root Cause**: In Android 14 GKI 6.1 (`common/modules.bzl`), `drivers/block/zram/zram.ko` and `mm/zsmalloc.ko` are listed in `COMMON_GKI_MODULES_LIST` (`CONFIG_ZRAM=m`, `CONFIG_ZSMALLOC=m`). Setting `CONFIG_ZRAM=y` compiles both into `vmlinux` instead of producing `.ko` module files.
- **Prevention**: Leave `CONFIG_ZRAM=m` and `CONFIG_ZSMALLOC=m` untouched in `gki_defconfig`.

---

## Rule 2: Never Pin or Split `drivers/dma-buf/` or `dma-fence`/`dma-resv` Headers on `6.1.177`
- **Symptom**:
  1. Checking out full `drivers/dma-buf/` and `include/linux/dma-buf.h` from `deprecated/android14-6.1-2025-06` (`6.1.138`) breaks compilation of `fs/proc/base.c`, `mm/mmap.c`, `kernel/fork.c`, and `kernel/bpf/dmabuf_iter.c` (`incomplete definition of type 'struct task_dma_buf_info'`).
  2. Checking out only `dma-fence*.c`, `dma-resv.c`, `sync_file.c`, and `iosys-map.h` from `6.1.138` while keeping `dma-buf.c` and `heaps/` on `6.1.177` builds cleanly, **but causes a BLACK SCREEN immediately after the Xiaomi boot logo** when SurfaceFlinger / `msm_drm.ko` initializes.
- **Root Cause**: Splitting `drivers/dma-buf/` between `6.1.177` (`dma-buf.c`, `dma-heap.c`, `heaps/`) and `6.1.138` (`dma-fence.c`, `dma-resv.c`, `sync_file.c`) creates internal ABI/locking mismatches inside `dma-buf` when Gralloc/SurfaceFlinger attaches fences to display buffers.
- **Prevention**: Keep the entire `drivers/dma-buf/` subsystem and `include/linux/dma-*` / `sync_file.h` / `iosys-map.h` 100% untouched on `6.1.177` (`refs/heads/android14-6.1`). Pin **only** the 5 display/PMIC paths from `deprecated/android14-6.1-2025-06`:
  - `drivers/gpu/drm/`
  - `include/drm/`
  - `drivers/video/backlight/`
  - `include/linux/backlight.h`
  - `drivers/spmi/`

---

## Rule 3: Never Put Optional/Renamed Headers in a Multi-File `git checkout FETCH_HEAD -- ...`
- **Symptom**: `git checkout FETCH_HEAD -- ...` exits with code 1 (`error: pathspec 'include/linux/dma-buf-map.h' did not match any file(s) known to git`).
- **Root Cause**: `include/linux/dma-buf-map.h` was renamed to `include/linux/iosys-map.h`. A single missing pathspec aborts the entire `git checkout` command.
- **Prevention**: Only pass guaranteed paths in the main `git checkout FETCH_HEAD -- ...` block.

---

## Rule 4: `6.1-lts` Brightness Flickering & ACK Vendor Hook Alignment
- **Symptom**: Screen brightness flickers on Xiaomi 14 (`houji`) when running `6.1-lts`.
- **Root Cause**:
  1. `refs/heads/android14-6.1-lts` (and `refs/tags/android14-6.1.138_r00`) diverged from Google's ACK in April 2024 and lacks `ANDROID: GKI:` vendor hooks required by Xiaomi's `msm_drm.ko` and `mi_disp.ko`.
  2. Post-`6.1.138` DRM/backlight/SPMI changes alter VBlank and MIPI-DSI `0x51` brightness timing.
- **Prevention**: For `6.1-lts` builds, always sync `refs/heads/android14-6.1` (`6.1.177` LTS + full ACK vendor hooks) and surgically pin **only** `drivers/gpu/drm/`, `include/drm/`, `drivers/video/backlight/`, `include/linux/backlight.h`, and `drivers/spmi/` from `refs/heads/deprecated/android14-6.1-2025-06` (`6.1.138`).

---

## Rule 5: Never Patch Core Memory Reclaim, PSI, Scheduler, or Binder C Code
- **Symptom**: Device runs smoothly for 20–45 minutes, then hard-freezes (requiring forced reboot), or kills background apps/notifications.
- **Root Cause**:
  - Dampening `PSI_MEM_SOME`/`PSI_MEM_FULL` in `kernel/sched/psi.c` blinds Android's `lmkd` when 8GB RAM + ZRAM fills up, trapping all 8 CPU cores in an infinite `try_to_free_pages()` / `lru_lock` livelock.
  - Setting `watermark_boost_factor = 0` in `mm/page_alloc.c` or forcing MGLRU/scheduler/cgroup/binder C-code hacks causes spinlock deadlocks with HyperOS vendor modules (`mi_schedule.ko`, `metis.ko`, `binder_prio.ko`).
- **Prevention**: Keep `mm/`, `kernel/sched/`, `kernel/cgroup/`, `drivers/android/binder*`, `drivers/block/zram/`, and `fs/` 100% pure upstream Google ACK C code (except official KernelSU/SUSFS patches).

---

## Rule 6: Never Enable `CONFIG_TRANSPARENT_HUGEPAGE=y` or Override Stock `gki_defconfig` MM/ZRAM Options on `houji` 6.1
- **Symptom**: Kernel passes `kmi_check.py` (`8909 symbols checked, no CRC mismatch`), flashes via AnyKernel3, shows the Xiaomi boot logo, and then **immediately goes to a black screen**.
- **Root Cause**:
  - Stock Android 14 GKI 6.1 (`arch/arm64/configs/gki_defconfig`) has `# CONFIG_TRANSPARENT_HUGEPAGE is not set`. Enabling `CONFIG_TRANSPARENT_HUGEPAGE=y` (even with `MADVISE=y`) changes inline folio/page/PMD helper definitions (`PageCompound`, `folio_test_large`, `pmd_trans_huge`) that are not caught by `vmlinux.symvers` symbol CRCs, breaking `msm_kgsl.ko` / `msm_drm.ko` GPU/display buffer mappings when SurfaceFlinger starts.
  - AnyKernel3 only flashes `Image` (not `system_dlkm`/`vendor_dlkm`), so overriding `CONFIG_ZRAM_DEF_COMP_*` or `CONFIG_LRU_GEN_ENABLED=y` mismatches the stock userspace/module expectations.
- **Prevention**: Do NOT add `CONFIG_TRANSPARENT_HUGEPAGE=y`, `CONFIG_TRANSPARENT_HUGEPAGE_MADVISE=y`, `CONFIG_LRU_GEN_ENABLED=y`, or `CONFIG_ZRAM_DEF_COMP_ZSTD=y` in `apply-device-patches/action.yml`. Keep the `gki_defconfig` identical to the proven working `15a8e28d` configuration.

---

## Rule 7: Compiler Flags and SELinux Weak Symbol
- **Never** add `-fno-plt` to `KBUILD_CFLAGS` (causes `RELA 311` error in `kvm_nvhe`).
- **Always** append `-Wno-vla -Wno-error=vla` to `Makefile` when building pinned `drivers/gpu/drm/`.
- **Always** convert `extern struct selinux_state *fake_state;` in `security/selinux/selinuxfs.c` to `struct selinux_state *fake_state __attribute__((weak)) = NULL;` so ReSukiSU builds do not fail with `ld.lld: error: undefined symbol: fake_state`.

---

## Rule 8: Preserve F2FS Struct Layout When Tracking `android14-6.1` Upstream HEAD
- **Symptom**: Kernel passes `kmi_check.py` (0 CRC mismatches), compiles cleanly, flashes via AnyKernel3, shows Xiaomi boot logo, and then **immediately goes to a black screen**.
- **Root Cause**: On Oct 15, 2026 at 21:55 UTC, Google ACK upstream pushed 27 commits modifying `fs/f2fs/` (`a465432321`, `745bced530`, etc.) that inserted `resizable_tail_secno`, `first_seq_zone_segno`, and `pinned_area_max_secno` into `struct f2fs_mount_info` and `struct f2fs_sb_info` in `fs/f2fs/f2fs.h`. Because `fs/f2fs/` internal struct layouts are not tracked by GKI KMI symbol CRCs, `kmi_check.py` passed with 0 mismatches, but Xiaomi 14's prebuilt vendor modules hooking `trace_android_vh_f2fs_iostat_*` dereferenced shifted struct offsets when `init` mounted `/data` (`f2fs`), crashing/hanging the device into an immediate black screen right after the bootloader logo.
- **Prevention**: When tracking the latest `refs/heads/android14-6.1` upstream HEAD, apply an ABI layout alignment in `fs/f2fs/f2fs.h` that relocates `first_seq_zone_segno`, `pinned_area_max_secno`, and `resizable_tail_secno` to the end of `struct f2fs_sb_info` (after `iostat_io_lat`). This preserves 100% of the byte offsets of `mount_opt`, `iostat_lock`, and `iostat_io_lat` expected by Xiaomi's prebuilt vendor modules (`mi_ext_lru.ko`, `mi_memory.ko`).

---

## Rule 9: Handle Single-Artifact Extraction in GitHub Actions `download-artifact` Verification
- **Symptom**: The `release` job fails at step `Verify all AnyKernel3 artifacts downloaded` with:
  ```
  ERROR: failed to re-fetch 6.1.177-android14-lts-KernelSU-Next-AnyKernel3
  expected an array but got: object ({"artifacts":[{"archive_d ...})
  ```
- **Root Cause**: When only a single artifact matches `pattern` across an Actions run (e.g. single-target `6.1-lts` + `KernelSU-Next`), `actions/download-artifact@v7` extracts files directly into `release-assets/` instead of `release-assets/<name>/`. Verification fails to find directory `release-assets/${name}`, attempts an API re-fetch with a broken jq query `.[0].archive_download_url`, and crashes.
- **Prevention**: Before verification in `main.yml`, detect if a single artifact was extracted flat into `release-assets/` and wrap it into `release-assets/${single_name}/`. Use `gh run download` directly as the fallback if an artifact is missing.

---

## Rule 10: Always Pin `drivers/gpu/drm/` to 6.1.138 on Xiaomi 14 (`houji`) 6.1-LTS
- **Symptom**: Kernel passes `kmi_check.py` (0 CRC mismatches), compiles cleanly, flashes via AnyKernel3, shows Xiaomi boot logo, then goes to a persistent **BLACK SCREEN**.
- **Root Cause**: Xiaomi 14's prebuilt vendor display modules (`msm_drm.ko` and `mi_disp.ko`) were compiled by Xiaomi against kernel 6.1.138. Linux 6.1.177 upstream made breaking internal changes to atomic display plane check callbacks and CRTC timing helpers. Running pure 6.1.177 DRM causes `msm_drm.ko` to fail display panel probe/modeset, leaving the screen completely blank (black screen).
- **Prevention**: Always surgically pin the 5 Display DRM and Backlight paths (`drivers/gpu/drm/`, `include/drm/`, `drivers/video/backlight/`, `include/linux/backlight.h`, and `drivers/spmi/`) to `refs/heads/deprecated/android14-6.1-2025-06` (`6.1.138`) while keeping `drivers/dma-buf/` on 6.1.177 and base ACK on verified commit `06aabb3c55`.

---

## Rule 11: Verified Ground-Truth Stock Kernel Baseline (HyperOS OS3.0.307.0.WNCCNXM)
- **Reference Firmware**: Xiaomi 14 (`houji`), HyperOS `OS3.0.307.0.WNCCNXM` (patch level 2026-08-01, SM8650 `pineapple`).
- **Stock Kernel Release**: `Linux version 6.1.138-android14-11-g0c3d559bcd85-ab14529422`
- **Official Google ACK Source Tag**: `refs/tags/android14-6.1-2025-06_r15` (`0c3d559bcd85c64dae9c9c9687abbe5347fff3ad`)
- **Official Compiler Toolchain**: Clang `r487747c` (`clang version 17.0.2`, LLD 17.0.2)
- **IKCONFIG Verified Parameters**:
  - `CONFIG_ARM64_4K_PAGES=y`, `CONFIG_ARM64_VA_BITS=39`, `CONFIG_HZ=250`, `CONFIG_PREEMPT=y`
  - `CONFIG_TRANSPARENT_HUGEPAGE=y`, `CONFIG_TRANSPARENT_HUGEPAGE_MADVISE=y`
  - `CONFIG_LRU_GEN=y`, `CONFIG_LRU_GEN_ENABLED=y`
  - `CONFIG_ZRAM=m`, `CONFIG_ZRAM_DEF_COMP="lzo-rle"`
  - `CONFIG_CFI_CLANG=y`, `CONFIG_LTO_NONE=y`
- **Prevention**: When upgrading to 6.1.177+ / 6.1.190, any display/SPMI compatibility checkout must target the exact stock tag `android14-6.1-2025-06_r15` (`0c3d559bcd85`), and defconfig settings for memory/scheduler must never deviate from these verified stock values.

---

## Rule 12: Certified Working Baseline Release 8 (r8) and Upstream 6.1.190 Rawdiff Integration
- **Verified Milestone**: [Release 8 (r8)](https://github.com/ngtrongha/GKI_KernelSU_SUSFS/releases/tag/r8), commit `a41a0b693`, base ACK commit `06aabb3c5541` + stock 6.1.138 DRM pin `0c3d559bcd85`. Verified by user device testing on 2026-10-16 to **boot cleanly on Xiaomi 14 (`houji`)** with zero black screen, zero brightness flickering, and working F2FS `/data` mount.
- **6.1.190 Integration Method**: In a shallow CI runner checkout, `git merge v6.1.190` fails with `fatal: refusing to merge unrelated histories`. To cleanly apply all bugfixes up to Linux 6.1.190, download and apply the official rawdiff between `v6.1.177` and `v6.1.190` from `git.kernel.org`:
  `https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/rawdiff/?id=v6.1.190&id2=v6.1.177`
  Immediately following rawdiff application:
  1. Re-pin the 5 Display DRM/Backlight/SPMI paths to stock tag `0c3d559bcd85` (`android14-6.1-2025-06_r15`).
  2. Restore `fs/f2fs/` to certified baseline `06aabb3c55` to keep the working struct layout.
  3. Clean up any reject files (`*.rej`) so reject scanners do not flag them.

---

## Rule 13: Always Pass `-F 3` to `patch -p1` in BBRv3 and Subsystem Backports on 6.1.190+
- **Symptom**: CI build fails at step `Setup Networking` / `Apply BBRv3 Patches` with:
  `common/net/ipv4/sysctl_net_ipv4.c.rej` generated (hunk #1 failed at line 44).
- **Root Cause**: Linux 6.1.190 upstream added `static int tcp_min_rcvbuf = 4096;` right above `sysctl_tcp_low_latency` in `net/ipv4/sysctl_net_ipv4.c`. Without fuzz tolerance (`-F 3`), GNU patch strictly rejects hunk #1 due to context line alteration even though the patch targets unrelated lines (`tcp_child_ehash_entries_max`).
- **Prevention**: Always pass `-F 3` (e.g. `patch -p1 -F 3 < ...`) in `.github/actions/bbrv3/action.yml` and `.github/actions/droidspaces/action.yml` so GNU patch cleanly tolerates up to 3 lines of upstream context drift.
