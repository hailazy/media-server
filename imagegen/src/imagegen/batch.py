"""Batch API support for image generation — 50% cost discount, 24h async.

Workflow:
  1. submit_batch(specs)  → uploads JSONL, creates batch, returns batch_id
  2. (24h passes)
  3. batch_status(id)     → poll status
  4. fetch_batch(id, out) → download + save images when status=completed

Use when:
  - Hai has N prompts known ahead of time (Phase 2 GDD deliverables, asset
    pipeline batches, overnight gen for next-day review)
  - 24h turnaround acceptable
  - Wants 50% cost discount vs sync

Skip for:
  - Interactive iteration (single image, immediate feedback)
  - Edit-from-reference workflow (faster sync feedback matters more)
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path

from .spec import GenSpec


def _client():
    if "OPENAI_API_KEY" not in os.environ:
        raise RuntimeError("OPENAI_API_KEY not set — export it, or load via --env-file")
    from openai import OpenAI
    return OpenAI()


def _spec_to_request(spec: GenSpec, custom_id: str) -> dict:
    """Convert GenSpec → batch JSONL request line."""
    body: dict = {
        "model": spec.model or "gpt-image-2",
        "prompt": spec.prompt,
        "n": spec.n,
        "size": spec.size,
        "quality": spec.quality,
        "output_format": spec.output_format,
        "output_compression": spec.output_compression,
    }
    # moderation only valid on generate, not edit
    if not spec.edit_ref:
        body["moderation"] = spec.moderation
    # passthrough extras
    body.update(spec.extra)

    # Endpoint URL determined by mode
    url = "/v1/images/edits" if spec.edit_ref else "/v1/images/generations"
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": url,
        "body": body,
    }


def submit_batch(specs: list[GenSpec], project: str = "") -> dict:
    """Submit a batch of image gen specs. Returns batch metadata dict.

    Args:
        specs: List of GenSpec — note edit_ref NOT supported in batch (needs
               file upload; batch only takes prompts).
        project: Optional tag stored in batch metadata for attribution.

    Returns:
        {"batch_id": str, "input_file_id": str, "n_requests": int,
         "estimated_cost_usd": float, "status": str}
    """
    if not specs:
        raise ValueError("No specs provided")
    # Reject edit_ref — Batch API can't upload reference images per-request
    if any(s.edit_ref for s in specs):
        raise ValueError(
            "Batch API doesn't support edit-from-reference (--edit-ref). "
            "Use sync mode for edit workflows."
        )

    client = _client()

    # Build JSONL
    lines = [_spec_to_request(s, f"req-{i:04d}") for i, s in enumerate(specs)]

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        temp_path = f.name

    try:
        # Upload
        with open(temp_path, "rb") as fh:
            file_obj = client.files.create(file=fh, purpose="batch")

        # Create batch
        endpoint = (
            "/v1/images/edits" if specs[0].edit_ref else "/v1/images/generations"
        )
        metadata = {"count": str(len(specs))}
        if project:
            metadata["project"] = project
        batch = client.batches.create(
            input_file_id=file_obj.id,
            endpoint=endpoint,
            completion_window="24h",
            metadata=metadata,
        )
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    # Rough cost estimate — sum of sync cost × 0.5 (batch discount)
    from .providers import get_provider
    prov = get_provider("gpt-image-2")
    est = sum(prov.estimate_cost(s) for s in specs) * 0.5

    return {
        "batch_id": batch.id,
        "input_file_id": file_obj.id,
        "n_requests": len(specs),
        "estimated_cost_usd": est,
        "status": batch.status,
    }


def batch_status(batch_id: str) -> dict:
    """Get current status + progress of a batch."""
    client = _client()
    batch = client.batches.retrieve(batch_id)
    rc = batch.request_counts
    return {
        "id": batch.id,
        "status": batch.status,
        "total": rc.total,
        "completed": rc.completed,
        "failed": rc.failed,
        "created_at": batch.created_at,
        "expires_at": batch.expires_at,
        "output_file_id": batch.output_file_id,
        "error_file_id": batch.error_file_id,
    }


def fetch_batch(batch_id: str, out_dir: Path, output_format: str = "jpeg") -> dict:
    """Download completed batch results to out_dir. Returns summary dict."""
    client = _client()
    batch = client.batches.retrieve(batch_id)

    if batch.status != "completed":
        raise RuntimeError(
            f"Batch status={batch.status}, cannot fetch yet "
            f"(completed={batch.request_counts.completed}/"
            f"{batch.request_counts.total})"
        )

    if not batch.output_file_id:
        raise RuntimeError("No output_file_id — batch may have failed entirely")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Download JSONL of responses
    content = client.files.content(batch.output_file_id).read()
    lines = content.decode("utf-8").strip().split("\n")

    saved: list[Path] = []
    errors: list[dict] = []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append({"line_err": str(e)})
            continue

        custom_id = entry.get("custom_id", "unknown")
        err = entry.get("error")
        if err:
            errors.append({"custom_id": custom_id, "error": err})
            continue

        response = entry.get("response", {})
        body = response.get("body", {})
        data_list = body.get("data", []) or []

        for i, item in enumerate(data_list):
            b64 = item.get("b64_json")
            if not b64:
                continue
            suffix = i if len(data_list) > 1 else None
            stem = custom_id if suffix is None else f"{custom_id}-{i}"
            out_path = out_dir / f"{stem}.{output_format}"
            out_path.write_bytes(base64.b64decode(b64))
            saved.append(out_path)

    return {
        "batch_id": batch_id,
        "saved_count": len(saved),
        "saved_paths": [str(p) for p in saved],
        "errors": errors,
    }


def load_specs_from_jsonl(path: Path) -> list[GenSpec]:
    """Parse a JSONL file of prompts/specs into GenSpec list.

    Each line is JSON. Required field: "prompt". All other fields optional
    (use GenSpec defaults). Example line:
        {"prompt": "iron cradle moss-covered exterior", "quality": "medium"}
    """
    specs: list[GenSpec] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Line {line_no} invalid JSON: {e}") from e
            if "prompt" not in obj:
                raise ValueError(f"Line {line_no} missing 'prompt' field")
            # Map fields → GenSpec
            kwargs: dict = {"prompt": obj["prompt"]}
            for k in (
                "provider", "model", "size", "quality", "n",
                "output_format", "output_compression", "moderation",
                "seed", "negative_prompt", "stream", "partial_images",
            ):
                if k in obj:
                    kwargs[k] = obj[k]
            if "extra" in obj:
                kwargs["extra"] = obj["extra"]
            specs.append(GenSpec(**kwargs))
    return specs
