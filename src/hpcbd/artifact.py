"""Artifact persistence: save/load trained bundle with integrity verification."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import joblib
import numpy as np


class ArtifactIntegrityError(Exception):
    """Raised when a loaded artifact fails its hash verification."""


# File names within the artifact directory
_PREPROCESSOR_FILE = "preprocessor.joblib"
_DETECTOR_FILE = "ensemble_detector.joblib"
_MANIFEST_FILE = "manifest.json"
_CONFIG_FILE = "config.json"


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_artifact(
    detector: Any,
    preprocessor: Any,
    tau: float,
    alpha: float,
    schema: list[str],
    config: dict[str, Any],
    path: str | os.PathLike,
) -> None:
    """Save a complete detection bundle with SHA-256 manifest.

    Parameters
    ----------
    detector : fitted EnsembleDetector (or any detector with score())
    preprocessor : fitted Preprocessor
    tau : float
        Calibrated decision threshold.
    alpha : float
        Significance level used for calibration.
    schema : list[str]
        Expected input column names.
    config : dict
        Experiment / training configuration.
    path : path-like
        Directory to save the artifact into. Created if absent.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    # Save components
    prep_path = path / _PREPROCESSOR_FILE
    det_path = path / _DETECTOR_FILE

    joblib.dump(preprocessor, prep_path)
    joblib.dump(detector, det_path)

    # Save config
    cfg_path = path / _CONFIG_FILE
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, default=str)

    # Build manifest
    files_to_hash = [prep_path, det_path, cfg_path]
    hashes = {fp.name: _sha256(fp) for fp in files_to_hash}

    manifest = {
        "version": "1.0",
        "tau": float(tau),
        "alpha": float(alpha),
        "schema": list(schema),
        "feature_names": list(getattr(preprocessor, "feature_names", [])),
        "hashes": hashes,
    }

    manifest_path = path / _MANIFEST_FILE
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"[artifact] Saved to {path}")
    print(f"  tau = {tau:.6f}, alpha = {alpha}")
    for name, h in hashes.items():
        print(f"  {name}: {h[:16]}…")


def load_artifact(
    path: str | os.PathLike,
) -> tuple[Any, Any, float, float, list[str], dict]:
    """Load and verify an artifact bundle.

    Returns
    -------
    (detector, preprocessor, tau, alpha, schema, config)

    Raises
    ------
    ArtifactIntegrityError
        If any file's hash does not match the manifest.
    FileNotFoundError
        If the artifact directory or manifest is missing.
    """
    path = Path(path)
    manifest_path = path / _MANIFEST_FILE
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest found at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Verify hashes
    for fname, expected_hash in manifest["hashes"].items():
        fpath = path / fname
        if not fpath.exists():
            raise ArtifactIntegrityError(f"File missing from artifact: {fname}")
        actual = _sha256(fpath)
        if actual != expected_hash:
            raise ArtifactIntegrityError(
                f"Hash mismatch for {fname}: expected {expected_hash[:16]}… got {actual[:16]}…"
            )

    # Load components
    preprocessor = joblib.load(path / _PREPROCESSOR_FILE)
    detector = joblib.load(path / _DETECTOR_FILE)

    # Load config
    cfg_path = path / _CONFIG_FILE
    with open(cfg_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    tau = float(manifest["tau"])
    alpha = float(manifest["alpha"])
    schema = list(manifest["schema"])

    return detector, preprocessor, tau, alpha, schema, config
