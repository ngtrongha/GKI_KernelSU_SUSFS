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
- **Prevention**: Leave `CONFIG_ZRAM=m` and `CONFIG_ZSMALLOC=m` untouched in `gki_defconfig`. Only set compressor choice options (`# CONFIG_ZRAM_DEF_COMP_LZ4 is not set`, `CONFIG_ZRAM_DEF_COMP_ZSTD=y`, `CONFIG_CRYPTO_ZSTD=y`).

---

## Rule 2: Never Overwrite `drivers/dma-buf/dma-buf.c` or `include/linux/dma-buf.h` on `6.1.177`
- **Symptom**: `fs/proc/base.c`, `mm/mmap.c`, `kernel/fork.c`, and `kernel/bpf/dmabuf_iter.c` fail to compile with:
  - `error: incomplete definition of type 'struct task_dma_buf_info'`
  - `error: call to undeclared function 'dma_buf_account_task' / 'put_dmabuf_info' / 'dma_buf_iter_begin'`
- **Root Cause**: Google's `refs/heads/android14-6.1` (`6.1.177`) added per-task dmabuf accounting (`struct task_dma_buf_info`) and BPF dmabuf iterators to `dma-buf.h` and `dma-buf.c`. Checking out `drivers/dma-buf/` or `include/linux/dma-buf.h` from `deprecated/android14-6.1-2025-06` (`6.1.138`) removes those declarations.
- **Prevention**: Keep `drivers/dma-buf/dma-buf.c` and `include/linux/dma-buf.h` on `6.1.177`. When pairing DMA-Fence with the `6.1.138` DRM pin, checkout **only** the fence/reservation/sync_file files:
  - `drivers/dma-buf/dma-fence*.c`, `drivers/dma-buf/dma-resv.c`, `drivers/dma-buf/sync_file.c`, `drivers/dma-buf/sw_sync.c`
  - `include/linux/dma-fence*.h`, `include/linux/dma-resv.h`, `include/linux/sync_file.h`

---

## Rule 3: Never Put Optional/Renamed Headers in a Multi-File `git checkout FETCH_HEAD -- ...`
- **Symptom**: `git checkout FETCH_HEAD -- ...` exits with code 1 (`error: pathspec 'include/linux/dma-buf-map.h' did not match any file(s) known to git`).
- **Root Cause**: `include/linux/dma-buf-map.h` was renamed to `include/linux/iosys-map.h`. A single missing pathspec aborts the entire `git checkout` command.
- **Prevention**: Only pass guaranteed paths in the main `git checkout FETCH_HEAD -- ...` block; checkout optional/renamed paths individually with `2>/dev/null || true`.

---

## Rule 4: `6.1-lts` Brightness Flickering & ACK Vendor Hook Alignment
- **Symptom**: Screen brightness flickers on Xiaomi 14 (`houji`) when running `6.1-lts`.
- **Root Cause**:
  1. `refs/heads/android14-6.1-lts` (and `refs/tags/android14-6.1.138_r00`) diverged from Google's ACK in April 2024 and lacks `ANDROID: GKI:` vendor hooks required by Xiaomi's `msm_drm.ko` and `mi_disp.ko`.
  2. Post-`6.1.138` DRM/backlight/SPMI changes alter VBlank and MIPI-DSI `0x51` brightness timing.
- **Prevention**: For `6.1-lts` builds, always sync `refs/heads/android14-6.1` (`6.1.177` LTS + full ACK vendor hooks) and surgically pin `drivers/gpu/drm/`, `include/drm/`, `drivers/video/backlight/`, `include/linux/backlight.h`, `drivers/spmi/`, and `dma-fence`/`sync_file` from `refs/heads/deprecated/android14-6.1-2025-06` (`6.1.138`). Never apply custom patches to `drivers/gpu/drm/` or `drivers/dma-buf/dma-fence.c`.

---

## Rule 5: Never Patch Core Memory Reclaim, PSI, Scheduler, or Binder C Code
- **Symptom**: Device runs smoothly for 20–45 minutes, then hard-freezes (requiring forced reboot), or kills background apps/notifications.
- **Root Cause**:
  - Dampening `PSI_MEM_SOME`/`PSI_MEM_FULL` in `kernel/sched/psi.c` blinds Android's `lmkd` when 8GB RAM + ZRAM fills up, trapping all 8 CPU cores in an infinite `try_to_free_pages()` / `lru_lock` livelock.
  - Setting `watermark_boost_factor = 0` in `mm/page_alloc.c` or forcing MGLRU/scheduler/cgroup/binder C-code hacks causes spinlock deadlocks with HyperOS vendor modules (`mi_schedule.ko`, `metis.ko`, `binder_prio.ko`).
- **Prevention**: Keep `mm/`, `kernel/sched/`, `kernel/cgroup/`, `drivers/android/binder*`, `drivers/block/zram/`, and `fs/` 100% pure upstream Google ACK C code (except official KernelSU/SUSFS patches). Tune only via safe `gki_defconfig` options (`CONFIG_LRU_GEN_ENABLED=y`, `CONFIG_TRANSPARENT_HUGEPAGE_MADVISE=y`, `# CONFIG_DAMON_RECLAIM is not set`).

---

## Rule 6: Compiler Flags, SELinux Weak Symbol, and KMI Safety
- **Never** add `-fno-plt` to `KBUILD_CFLAGS` (causes `RELA 311` error in `kvm_nvhe`).
- **Always** append `-Wno-vla -Wno-error=vla` to `Makefile` when building pinned `drivers/gpu/drm/`.
- **Always** convert `extern struct selinux_state *fake_state;` in `security/selinux/selinuxfs.c` to `struct selinux_state *fake_state __attribute__((weak)) = NULL;` so ReSukiSU builds do not fail with `ld.lld: error: undefined symbol: fake_state`.
- **Never** alter exported KMI struct definitions in `include/linux/` or enable `CONFIG_TRANSPARENT_HUGEPAGE_ALWAYS=y`.
