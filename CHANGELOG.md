# Changelog

## 2.0.0-dev.11 - 2026-09-12

- Fixed 24 GB GPU out-of-memory failures by removing the TE-Speed layer cache from all bundled H3 workflows; retained INT8/SageAttention and added four-way low-VRAM attention and feed-forward chunking.
- Fixed the remake action for a failed segment with no saved successful record so it resumes the existing project pipeline from its checkpoint instead of blocking the user.
- Added safe, project-scoped stopping for the full production pipeline, individual and batch asset generation, failed-segment retries, and guided outline/script/prompt generation.
- Persisted `running`, `stopping`, and `stopped` states so refresh or service restart restores a clear task state and users can continue from saved results.
- Preserved completed assets, prompts, and video segments when stopping; stale pages cannot stop a newer run.
- Added exact ComfyUI job cancellation when supported and exact pending-job deletion on older versions, without calling the global interrupt endpoint or affecting unrelated queue items.
- Isolated the Windows development Web server on `127.0.0.1:7862`, separate from the production default `7861`.
- Made the development launcher reject IPv4, wildcard, IPv6, non-HTTP, or unhealthy services already listening on port 7862.
- Added regression coverage for stop/completion races, refresh recovery, partial prompt preservation, project ownership, cross-process locks, and development-port detection.

## 2.0.0-dev.10 - 2026-09-12

- Added a per-segment retry action when an H3 video segment fails.
- Retrying regenerates only the selected failed segment and preserves completed segments.
- Added persisted production and retry states that recover after page refresh or service restart.
- Added per-project locking to prevent duplicate full-pipeline and segment-retry jobs.
- Kept successfully generated segments available when final FFmpeg composition fails.
- Added regression coverage for retry isolation, interrupted-state recovery, duplicate-job protection, and finalization failures.

## 2.0.0-dev.9 - 2026-09-12

- Established the standalone AIX Drama Factory V2 open-source repository with a clean, independent history.
- Licensed the AIX project code as `AGPL-3.0-only`, added the canonical license text, documented third-party boundaries, and exposed a source-code link in the Web interface.
- Removed personal payment QR images and excluded archives, credentials, user projects, generated media, runtimes, models, logs, caches, and backups from the public source snapshot.
- Restored the backend `/api/comfy/queue` proxy omitted by the first dev.9 updater build and switched the source frontend away from the hard-coded `127.0.0.1:8189` endpoint.

- Fixed managed exclusive mode so ComfyUI and Qwen are actually stopped, verified offline, and switched safely on Linux hosts.
- Added trusted host-side service command hooks without exposing arbitrary shell commands through Web settings.
- Added ComfyUI workflow preflight with clear missing-node guidance, including ComfyUI-GGUF.
- Added installed-model detection and same-family H3 model resolution for FL2VA and Ref2VA workflows.
- Corrected H3 frame alignment and capped 15-second segments at 362 frames to reduce invalid workloads and GPU memory pressure.
- Added queue-safe ComfyUI memory release and one controlled retry for H3 out-of-memory failures.
- Treated non-verbal markers such as no-dialogue grunts as action instead of required spoken dialogue.
- Made batch prompt generation preserve successful segments, continue after individual failures, and retry only failed segments later.
- Added conservative cross-platform ComfyUI enum resolution so Windows workflow model paths automatically match the exact Linux UNET, LoRA, VAE, and encoder names exposed by the connected server.
- Made H3 prompt validation deterministic for dialogue: pure bracketed actions/no-dialogue markers move into action, spoken words after an action cue remain intact, and missing/duplicated source dialogue is placed exactly once inside Storyboard before any LLM repair.
- Soft Chinese-control warnings no longer force a full prompt redraw; real structural, reference, or unauthorized-dialogue errors remain blocking.
- Fixed guided prompt retries so successful segment prompts remain cached, failures no longer raise an uninitialized-error exception, and later retries generate only missing or invalid segments.
- Fixed H3 OOM recovery timing by waiting for the failed prompt itself to leave the ComfyUI queue before performing a queue-safe cache unload and one controlled retry; unrelated queued work is never interrupted.
- Rebuilt the Windows incremental updater with ASCII-only PowerShell source so Windows PowerShell 5.1 no longer corrupts UTF-8 Chinese strings into parser errors.
- Reduced prompt-stage failures with deterministic stage-direction cleanup, exact Storyboard dialogue placement, non-blocking soft warnings, and retry-only-failed segment caching.

## 2.0.0-dev.8 - 2026-09-08

- Added backward-compatible managed and external runtime modes for ComfyUI and local Qwen.
- Guaranteed that external services are never automatically started, stopped, or included in low-VRAM process switching.
- Made ComfyUI, llama.cpp, Qwen model, mmproj, FFmpeg, service URL, Web host, and Web port configurable.
- Added a settings UI for existing ComfyUI/Qwen connections, advanced runtime paths, and read-only connection diagnostics.
- Added `/api/runtime/preflight` and runtime-mode details to `/api/status`.
- Added a standalone Web launcher, pinned Web dependencies, runtime regression tests, three-module distribution guidance, and release/model manifest templates.
- Added Git ignore rules for timestamped root backup files.

## 2.0.0-dev.7 - 2026-08-28

- Added enforced desktop safe mode for the Windows Alpha launcher: only versioned Desktop API routes and read-only project media are available.
- Blocked legacy production and generation routes with HTTP 403 while desktop safe mode is active.
- Added a capability flag that lets the launcher reject an existing backend unless it is the expected V2 API running in safe mode.
- Added regression coverage proving the legacy pipeline cannot be started from the desktop Alpha connection.
- Added an environment switch that starts the V2 Web backend without opening its legacy browser page.

## 2.0.0-dev.6 - 2026-08-26

- Added a versioned, localhost-only desktop API for capabilities, environment status, project listing, safe draft creation, draft updates, and project reading.
- Kept desktop draft creation separate from production so opening the Alpha interface cannot start GPU generation unexpectedly.
- Added sanitized desktop project views that omit machine-specific asset paths and never mutate saved projects during reads.
- Added desktop API tests for validation, progress normalization, safe updates, legacy project reads, and dynamic service status.

## 2.0.0-dev.5 - 2026-08-25

- Added live progress for single-asset prompt edits and regenerations.
- Connected guided preproduction approval to the existing H3 video pipeline and restored finished guided projects correctly from history.
- Reworked generated H3 prompts around validated natural Chinese dialogue, independent voice identity, first-frame continuity, and no-subtitle constraints.
- Added optional storyboard generation and optional storyboard references during H3 production.
- Promoted the production unit from one camera shot to one 8–15 second narrative segment containing multiple continuous shots.
- Added automatic previous-segment tail-frame extraction for continuity-dependent segments while preserving independent openings and transitions.
- Fixed the V2 ComfyUI launcher path and added persisted per-segment generation time.
- Prepared the source repository for future public release without bundling models, runtimes, generated media, project data, logs, or backups.
- Replaced tracked machine-specific settings with safe example configuration files.
- Removed hard-coded installation paths from documentation and service shutdown checks.
- Added public setup, repository-boundary, versioning, and large-file guidance.

## 2.0.0-dev.4 - 2026-08-24

- Added persisted ComfyUI sampling progress to every V2 preparation asset and storyboard card.
- Added live per-card status, percentage, sampling-step detail, batch overall progress, success count, and failure count.
- Added server-side guards against starting, uploading, or regenerating an item while a batch is active.
- Preserved progress state when rebuilding an asset plan and restored it after page refresh from the project JSON.

## 2.0.0-dev.3 - 2026-08-24

- Replaced per-image generate/confirm clicks with a persisted batch asset workflow.
- Automatic mode now generates every missing asset and storyboard image on entering the review step.
- Custom-reference mode now accepts any subset of uploads, then generates all remaining images from one final button.
- Added batch progress, refresh recovery, retry of missing images, one-click approval of all ready images, and retained single-image upload/regeneration for exceptions.

## 2.0.0-dev.2 - 2026-08-24

- Fixed Qwen 8085 startup failure caused by a Chinese shared-model path being corrupted by `cmd.exe`.
- Added a local model-directory junction and direct Python launch of `llama-server.exe` for reliable on-demand startup.
- Added queue-aware Qwen/ComfyUI stage switching: active ComfyUI work is never interrupted, while idle GPU services can be switched automatically.
- Recovered the pending outline request and preserved the current project state through script confirmation and H3 prompt preparation.

## 2.0.0-dev.1 - 2026-08-24

- Added a guided preproduction workflow with review gates for story, outline, script, and per-shot H3 prompts.
- Kept both story/script generation and full H3 timeline prompt entry modes.
- Added character, scene, prop, and storyboard image planning with upload or AI generation per item.
- Added editable image prompts, single-item regeneration, explicit approval, and refresh-safe project state.
- Kept the legacy one-click production path available behind the guided-flow toggle.

## 2.0.0-dev.0 - 2026-08-24

- Created an isolated AIX V2 development environment.
- Assigned Web 7861, ComfyUI 8190, and Qwen 8085.
- Added a startup guard that refuses to compete with stable GPU services.
- Kept projects, assets, outputs, configuration, logs, and backups independent.
- Shared large ComfyUI and Qwen model files without copying them.
