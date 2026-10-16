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
