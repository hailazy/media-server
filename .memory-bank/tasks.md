# Tasks

## Documentation Cleanup and Normalization
Last performed: 2025-10-27

Files to modify (primary):
- [docs/README.md](docs/README.md:1)
- [docs/QUICK-REF.md](docs/QUICK-REF.md:1)
- [docs/PODMAN.md](docs/PODMAN.md:1)
- [docs/GPU-TIMING-FIX.md](docs/GPU-TIMING-FIX.md:1)
- [docs/BOOT-STARTUP-INVESTIGATION.md](docs/BOOT-STARTUP-INVESTIGATION.md:1)
- [docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md](docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md:1)
- [docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md](docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md:1)

Files to verify (secondary):
- [core/podman-compose.yml](core/podman-compose.yml:1) (line anchors used in docs)
- [maintenance/maintenance.sh](maintenance/maintenance.sh:1), [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1)
- [scripts/podman-up.sh](scripts/podman-up.sh:1), [scripts/podman-down.sh](scripts/podman-down.sh:1), [scripts/podman-logs.sh](scripts/podman-logs.sh:1), [scripts/podman-systemd-wrapper.sh](scripts/podman-systemd-wrapper.sh:1)

Steps:
1) Remove all “Roocline” mentions
   - Search and replace across docs for: roocline/rootcline/roccline/roo[-_ ]?cline
2) Standardize script and compose usage
   - Replace root-level helpers (start.sh/stop.sh/logs.sh/debug.sh) with:
     - Start: `./scripts/podman-up.sh`
     - Stop: `./scripts/podman-down.sh`
     - Logs: `./scripts/podman-logs.sh`
     - Quick debug: `./maintenance/quick-debug.sh`
   - Ensure compose commands always specify the file: `podman-compose -f core/podman-compose.yml ...`
3) Fix systemd references
   - Use code form for user-level unit path: `~/.config/systemd/user/media-stack.service`
   - Avoid linking to files outside repo; keep them inline as code
4) Normalize links
   - Use clickable references with line anchors for repo files, e.g. [core/podman-compose.yml](core/podman-compose.yml:1)
   - Fix all relative links pointing up or into sibling docs
5) Validate commands and examples
   - Ensure all commands run from repo root unless a preceding `cd` is shown
   - Prefer `podman-compose -f core/podman-compose.yml ...` over implicit context
6) Optional code-level echoes (not required for docs pass)
   - In [scripts/podman-logs.sh](scripts/podman-logs.sh:1) and [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1), update helper “Useful commands” echoes to remove non-existent root scripts (start.sh/logs.sh) if present

Validation:
- Search for removed tools and vendor wording:
  - start.sh|stop.sh|logs.sh|debug.sh (only allowed in historical notes or examples marked clearly)
  - roocline|rootcline|roccline|roo[-_ ]?cline (should be zero)
- Spot check all clickable references resolve to repo paths:
  - [core/podman-compose.yml](core/podman-compose.yml:1)
  - [scripts/podman-up.sh](scripts/podman-up.sh:1)
  - [maintenance/maintenance.sh](maintenance/maintenance.sh:1)

## Documentation Reorganization with Index
Last performed: 2025-10-27

Files to modify (eight docs):
- [docs/QUICK-REF.md](docs/QUICK-REF.md:1)
- [docs/README.md](docs/README.md:1)
- [docs/PODMAN.md](docs/PODMAN.md:1)
- [docs/GPU-TIMING-FIX.md](docs/GPU-TIMING-FIX.md:1)
- [docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md](docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md:1)
- [docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md](docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md:1)
- [docs/BOOT-STARTUP-INVESTIGATION.md](docs/BOOT-STARTUP-INVESTIGATION.md:1)
- [docs/AIRVPN-VALIDATION-CHECKLIST.md](docs/AIRVPN-VALIDATION-CHECKLIST.md:1)

Steps:
1) Insert two-line banner (immediately under H1, do not change titles)
   - Format:
     - Start here: [docs/INDEX.md](docs/INDEX.md:1)
     - Reading order: N/8 • Label
   - Reading order:
     - QUICK-REF 1/8 • Essential
     - README 2/8 • Essential
     - PODMAN 3/8 • Essential
     - GPU-TIMING-FIX 4/8 • Optional (NVIDIA only)
     - QBITTORRENT-PERFORMANCE-OPTIMIZATION 5/8 • Optional
     - JELLYFIN-PERFORMANCE-OPTIMIZATION 6/8 • Optional
     - BOOT-STARTUP-INVESTIGATION 7/8 • Historical/Case Study (Optional)
     - AIRVPN-VALIDATION-CHECKLIST 8/8 • Optional (Validation/Deep dive)

2) Normalize commands to compose usage from repo root
   - Ensure all examples use: podman-compose -f core/podman-compose.yml …
   - Update logs/exec/ps/restart/pull/down/up examples accordingly
   - Keep podman healthcheck run … as-is (no compose equivalent)

3) Link normalization
   - Convert any repo-internal “../” links to root-relative clickable references with :1 anchors:
     - [core/podman-compose.yml](core/podman-compose.yml:1), [scripts/podman-up.sh](scripts/podman-up.sh:1), etc.
   - Do not alter external URLs
   - Do not rewrite non-link code paths (e.g., ../configs in volume mounts/commands)

4) AIRVPN checklist special fixes
   - Replace any “cd core …” patterns with root-executed compose commands
   - Replace “podman exec gluetun …” with “podman-compose -f core/podman-compose.yml exec gluetun …”
   - Change “ls -la ../configs/” to “mkdir -p configs && ls -la configs/”
   - Add note: “All commands assume execution from the repository root.”

5) README cleanup
   - Remove any stray artifacts; ensure file ends cleanly after the last intended paragraph

Validation checklist:
- [ ] Banners present under H1 and show correct reading order/labels
- [ ] All internal repo links are root-relative and include :1 anchors
- [ ] All podman-compose examples include “-f core/podman-compose.yml”
- [ ] AIRVPN checklist uses repo-root commands; “gluetun” calls use compose exec; configs path fixed with mkdir hint
- [ ] README has no trailing stray text; clean EOF

Notes:
- Single compose source of truth: [core/podman-compose.yml](core/podman-compose.yml:1)
- First-stop index for readers: [docs/INDEX.md](docs/INDEX.md:1)

## Memory Bank Initialization
Last performed: 2025-10-27

Files to create/update:
- [`.kilocode/rules/memory-bank/product.md`](.kilocode/rules/memory-bank/product.md:1)
- [`.kilocode/rules/memory-bank/context.md`](.kilocode/rules/memory-bank/context.md:1)
- [`.kilocode/rules/memory-bank/architecture.md`](.kilocode/rules/memory-bank/architecture.md:1)
- [`.kilocode/rules/memory-bank/tech.md`](.kilocode/rules/memory-bank/tech.md:1)
- [`.kilocode/rules/memory-bank/tasks.md`](.kilocode/rules/memory-bank/tasks.md:1) (this file)
- Update path references in [`.kilocode/rules/memory-bank/memory-bank-instructions.md`](.kilocode/rules/memory-bank/memory-bank-instructions.md:1) to use rules/ not rule/

Steps:
1) Product
   - Document purpose, problems solved, high-level flow, UX goals
   - Include clickable references to [docs/README.md](docs/README.md:1), [docs/QUICK-REF.md](docs/QUICK-REF.md:1), [docs/PODMAN.md](docs/PODMAN.md:1)
2) Architecture
   - Capture system diagram, component relationships, critical paths
   - Reference [core/podman-compose.yml](core/podman-compose.yml:1), [scripts](scripts/podman-up.sh:1), [maintenance](maintenance/maintenance.sh:1)
3) Tech
   - List technologies, constraints (rootless, SELinux), dependencies
   - Provide standard tool usage patterns with exact commands
4) Context
   - Current work focus, recent changes, next steps
   - Canonical paths and assumptions
5) Tasks
   - Store repeatable workflows (this file)
6) Instructions file alignment
   - Ensure references to the Memory Bank directory use [`.kilocode/rules/memory-bank/`](.kilocode/rules/memory-bank) consistently

Important considerations:
- Do not edit [`.kilocode/rules/memory-bank/brief.md`](.kilocode/rules/memory-bank/brief.md:1); it’s user-owned
- Keep links clickable with line anchors to reduce drift
- Favor rootless-first guidance and document rootful trade-offs in [docs/PODMAN.md](docs/PODMAN.md:1)

Example verification checklist after initialization:
- [x] All five core files exist under [`.kilocode/rules/memory-bank/`](.kilocode/rules/memory-bank)
- [x] Path references in [memory-bank-instructions.md](.kilocode/rules/memory-bank/memory-bank-instructions.md:1) use rules/
- [x] Docs reference only supported scripts and the single compose file: [core/podman-compose.yml](core/podman-compose.yml:1)