# Jellyfin Performance Optimization

> Hardware-tuned configuration for **RTX 4070 Ti SUPER + Ryzen 5 7600X3D + 32GB RAM + NVMe**.
> Source of truth: `media/compose.yml` jellyfin service + `media/.env` performance section.
> Last revised: 2026-05-03 (post home-server migration).

## TL;DR

The current config targets **8-12 concurrent HEVC/H.264 transcodes or 4-6 AV1 transcodes** on this hardware. If you only stream 1-2 clients, most of these knobs don't matter — direct-play takes the GPU/CPU path of least resistance. The settings below earn their cost only when transcoding gets heavy or library scanning hits NVMe + tmpfs simultaneously.

---

## 1. Hardware baseline

| Component | Spec | What it buys |
|-----------|------|-------------|
| GPU | NVIDIA RTX 4070 Ti SUPER (16GB VRAM) | NVENC + NVDEC for AV1 / HEVC / H.264 (encode + decode); 8th-gen NVENC, 5th-gen NVDEC |
| CPU | AMD Ryzen 5 7600X3D (6c / 12t) | 3D V-Cache reduces ffmpeg muxing latency; threads 0-9 pinned to Jellyfin |
| RAM | 32GB DDR5 | 12GB hard cap for Jellyfin, 20GB tmpfs transcode cache (RAM-backed) |
| Storage | NVMe (system + media) | `noatime` + `blkio_weight=1000` priority |

VRAM budget per session (rough):
- HEVC 4K decode + 1080p encode: ~1.5GB
- AV1 4K decode + 1080p encode: ~2GB
- Idle (no active transcode): ~300MB

The hard ceiling that matters is the **shared VRAM pool with Forge** (12GB peak when SDXL gen runs). `scripts/vram-guard.sh` enforces a 13GB soft warn / 15GB hard refuse before starting GPU-using sections.

---

## 2. Current settings (annotated)

### 2.1 GPU enablement
```yaml
environment:
  - NVIDIA_VISIBLE_DEVICES=all
  - NVIDIA_DRIVER_CAPABILITIES=video,compute,utility,graphics
  - NVIDIA_GPU_MEMORY_FRACTION=0.8     # cap at 80% of 16GB = 12.8GB
  - NVIDIA_NVENC_H264=1
  - NVIDIA_NVENC_HEVC=1
  - NVIDIA_NVENC_AV1=1                 # 4070 Ti SUPER supports AV1 encode (Ada Lovelace)
  - NVIDIA_NVDEC_H264=1
  - NVIDIA_NVDEC_HEVC=1
  - NVIDIA_NVDEC_AV1=1
devices:
  - "nvidia.com/gpu=all"               # CDI device — preferred for rootless Podman
  - "/dev/dri:/dev/dri"                # VAAPI fallback (rarely used; intel iGPU absent on AM5)
```

CDI (`nvidia.com/gpu=all`) is the modern Podman path. The legacy `--gpus all` flag is incompatible with rootless. Driver version is auto-tracked; `_lib.sh:check_nvidia_cdi_configuration` regenerates `~/.config/containers/cdi/nvidia.yaml` on driver upgrade.

### 2.2 CPU pinning
```yaml
cpus: "5.0"            # 5 cores' worth of time slice
cpu_shares: 2048       # higher priority than qBittorrent (1024)
cpuset_cpus: "0-9"     # threads 0-9 (5 physical cores × SMT)
```

Threads 10-11 (last physical core) are reserved for system + qBittorrent (`cpuset_cpus: "10-11"`). This isolation prevents transcode bursts from starving the VPN namespace.

### 2.3 Memory + tmpfs
```yaml
mem_limit: 12g         # hard cap
mem_reservation: 8g    # guaranteed allocation
memswap_limit: 12g     # equal to mem_limit → no swap
oom_kill_disable: true # prefer hang over kill (controversial — see Anti-patterns)

tmpfs:
  - /tmp/jellyfin:size=20G          # general scratch
  - /cache/transcode:size=20G       # active transcode segments
  - /var/cache/jellyfin:size=2G     # ffprobe + image cache
shm_size: 2gb                       # GPU-CPU shared memory
```

20GB transcode tmpfs is RAM-backed — instant seeks, zero NVMe wear. With 32GB system RAM, this leaves ~12GB for system + qBT + Forge cohabitation. If you bump `mem_limit` past 16GB, expect tmpfs evictions to swap.

### 2.4 ffmpeg / probing
```yaml
- JELLYFIN_FFMPEG_ANALYZE_DURATION=2000000   # 2s analysis (default 5s) — speeds first-frame
- JELLYFIN_FFMPEG_PROBESIZE=1000000000       # 1GB probe — forces deep stream inspection
- JELLYFIN_MAX_MUXING_QUEUE_SIZE=2048        # large queue prevents stalls on bursty seeks
- JELLYFIN_MAX_CONCURRENT_TRANSCODES=10
- JELLYFIN_THREAD_COUNT=10                   # match cpuset
```

`PROBESIZE=1GB` is heavy — it's the cost of correctly identifying weird MKV streams (multiple audio tracks, embedded fonts). Drop to `100000000` (100MB) if first-play latency is annoying.

### 2.5 I/O + ulimits
```yaml
blkio_weight: 1000     # max NVMe priority (qBT is 500)
ulimits:
  memlock: { soft: -1, hard: -1 }     # unlimited locked pages (mmap'd library DB)
  nofile: { soft: 262144, hard: 262144 }  # 256K open files (large libraries)
  nproc:  { soft: 65536,  hard: 65536  }
```

These are cheap insurance — they prevent the "library suddenly slow after 30K episodes" failure mode.

---

## 3. Tuning knobs

When to change what, and what breaks if you push too hard.

### 3.1 More concurrent transcodes
**Knob:** `JELLYFIN_MAX_CONCURRENT_TRANSCODES`
- Current: 10 (safe for 4070 Ti SUPER + 16GB VRAM)
- Up to ~12 for HEVC-heavy mix — beyond that, NVENC quality engine queue becomes the bottleneck
- Drop to 6 if Forge runs concurrently (VRAM contention)

**Verify:** `nvidia-smi dmon -s u` during transcodes — encoder utilization >90% sustained = saturated.

### 3.2 Bigger / smaller transcode cache
**Knob:** `tmpfs /cache/transcode:size=`
- Current: 20G (RAM)
- Raise to 30G if you have spare RAM and stream a single 4K HEVC source repeatedly (cache hits)
- Drop to 10G if running Forge SDXL alongside (RAM contention)
- Switch to NVMe-backed (remove `tmpfs:`, use `volumes:`) only if you hit RAM cap regularly — wears NVMe but saves 20GB RAM

### 3.3 Reduce first-play latency
**Knob:** `JELLYFIN_FFMPEG_PROBESIZE` + `JELLYFIN_FFMPEG_ANALYZE_DURATION`
- Current: 1GB / 2s — thorough but slow
- Drop probesize to 100MB (`100000000`) for ~500ms faster first-frame on most files
- Symptom of probesize too low: subtitle tracks missing on first play, appear after restart

### 3.4 Library scan throughput
Library scans are CPU + I/O bound, not GPU. To speed up:
- `cpu_shares` is already 2048 (max). Can't go higher.
- Bigger `tmpfs /var/cache/jellyfin` (currently 2GB) only helps if you have many thousand items
- True fix: keep media on NVMe, not spinning disks

---

## 4. Codec strategy

### 4.1 NVENC presets (RTX 4070 Ti SUPER, Ada NVENC)
Set in Jellyfin Dashboard → Playback → Hardware acceleration → Encoding presets.

| Preset | Speed | Quality | Use case |
|--------|-------|---------|----------|
| p1 | Fastest | Lowest | Mobile / low-bandwidth, quality acceptable |
| p3 | Fast | Acceptable | Default for most clients |
| **p4** | Balanced | Good | **Current setting** — best ratio for this GPU |
| p5 | Slow | Better | Single high-quality stream, no time pressure |
| p7 | Slowest | Best | Archive / one-shot encodes (don't use for live transcode) |

`.env` has `JELLYFIN_TRANSCODE_H264_PRESET=p4`, `JELLYFIN_TRANSCODE_HEVC_PRESET=p4`, `JELLYFIN_TRANSCODE_AV1_PRESET=5` (AV1 uses 1-7 scale, 5 ≈ p4). Jellyfin reads these as hints; actual preset is set in UI.

### 4.2 When to enable AV1
- **Yes**: ≥1080p target, client supports AV1 (Chromecast Ultra, modern smart TVs, Chrome 100+)
- **No**: 4K → 1080p downscale where source is HEVC. NVENC HEVC is mature; AV1 here gains <5% bitrate at 2x encode cost.
- **Rule**: AV1 wins on bitrate, HEVC wins on encoder maturity. Default to HEVC; use AV1 only for known-compatible clients.

### 4.3 Decode strategy
NVDEC handles all formats this GPU supports (H.264/HEVC/AV1, 8-bit and 10-bit). VAAPI fallback (`/dev/dri`) exists but won't activate — RTX 4070 Ti SUPER + AM5 means no Intel iGPU.

`.env` order: `JELLYFIN_HW_DECODE_PRIORITY=nvdec,vaapi,qsv` (QSV requires Intel CPU; entry is harmless).

---

## 5. Verification

### 5.1 Live transcode probe
```bash
# Watch GPU during a 4K HEVC → 1080p transcode
nvidia-smi dmon -s pucvmet -d 1
# Columns: power, util, mem-bw, temp, encoder util, decoder util

# Container resource view
podman stats jellyfin --no-stream
```

Expected during 1× 4K HEVC transcode:
- GPU util: 25-40%
- ENC util: 60-80%
- DEC util: 30-50%
- VRAM: ~1.8-2.5GB used by jellyfin process
- CPU (container): 150-300% (1.5-3 cores)

### 5.2 Jellyfin diagnostic
Dashboard → Playback → Live transcoding → click active stream → reveals:
- Source codec / target codec
- Direct-play vs transcode reason
- Bitrate / FPS

If `Reason: codec not supported` but client *does* support it → check `Codecs` profile in Dashboard → Playback → Profiles.

### 5.3 ffmpeg log (when transcode fails)
```bash
podman exec jellyfin tail -f /config/log/ffmpeg-transcode-*.log
```

Common failure: `unknown encoder 'av1_nvenc'` → driver too old. RTX 4070 Ti SUPER needs ≥530.30.

---

## 6. Anti-patterns

Configuration ideas that look helpful but degrade this setup:

### `oom_kill_disable: true` is a tradeoff, not a win
Currently set. Pros: prevents the kernel from murdering Jellyfin during transient memory spikes (library scan + transcode collision). Cons: if jellyfin actually leaks, you'll see a hung container instead of a clean restart. Keep enabled but watch `podman events` for `oom` warnings.

### Don't enable `tmpfs` for `/config`
The Jellyfin SQLite library lives in `/config`. Putting it on tmpfs = wipe on restart. The compose mounts `./data/jellyfin:/config:Z` (NVMe-backed) intentionally.

### Don't bump `JELLYFIN_THREAD_COUNT` past `cpuset_cpus` width
`cpuset_cpus: "0-9"` = 10 logical threads available. `JELLYFIN_THREAD_COUNT=10` matches. Setting to 16 or 24 just causes thread thrashing on a 12-thread CPU.

### Don't set both `cpus:` and rely on `cpu_shares` alone
`cpus: "5.0"` is a hard time-slice cap; `cpu_shares: 2048` is relative weight under contention. They're complementary, not redundant. Removing `cpus` lets transcode bursts steal time from system processes.

### Don't enable QuickSync (QSV) "for fallback"
This system has no Intel iGPU. QSV setup just adds a missing-device error to the log on every startup probe. The harmless `qsv` entry in `JELLYFIN_HW_DECODE_PRIORITY` is fine; explicit `--hwaccel qsv` ffmpeg overrides will fail.

### Don't run `podman exec jellyfin` ffmpeg manually expecting tmpfs persistence
Files in `/cache/transcode` are RAM-backed and segment-scoped. Active transcode segments get cleaned every few seconds.

---

## 7. Reference: env vars used by Jellyfin

From `media/.env` (sourced via compose):

| Var | Default | Purpose |
|-----|---------|---------|
| `JELLYFIN_CPU_THREADS` | 10 | Thread count hint |
| `JELLYFIN_CPU_AFFINITY` | 0-9 | cpuset_cpus |
| `JELLYFIN_MEMORY_HARD_LIMIT` | 12884901888 | mem_limit (12GB) |
| `JELLYFIN_MEMORY_SOFT_LIMIT` | 8589934592 | mem_reservation (8GB) |
| `JELLYFIN_TRANSCODE_CACHE_SIZE` | 20G | tmpfs size hint |
| `JELLYFIN_MAX_TRANSCODES` | 10 | concurrent encode jobs |
| `JELLYFIN_TRANSCODE_H264_PRESET` | p4 | NVENC quality preset |
| `JELLYFIN_TRANSCODE_HEVC_PRESET` | p4 | NVENC quality preset |
| `JELLYFIN_TRANSCODE_AV1_PRESET` | 5 | AV1 quality (1-7 scale) |

These are documented in `media/.env` itself; treat that file as canonical for hardware-specific values.

---

## See also
- `../INDEX.md` — current home-server doc index
- `../../media/compose.yml` — jellyfin service definition
- `../../media/.env` — performance variables (live values)
- `../../scripts/vram-guard.sh` — VRAM budgeting between Jellyfin and Forge
- `BOOT-STARTUP-INVESTIGATION.md` — first-boot GPU race investigation
- `GPU-TIMING-FIX.md` — CDI auto-regen technique
