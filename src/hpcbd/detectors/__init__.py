"""Anomaly detector implementations."""

from .mahalanobis import MahalanobisDetector
from .pca import PCADetector
from .iforest import IForestDetector
from .knn import KNNDetector
from .gmm import GMMDetector
from .ocsvm import OCSVMDetector
from .pyod_ecod import PyODECODDetector
try:
    from .river_hst import RiverHalfSpaceTreesDetector
except ImportError:
    # River is optional for batch training; streaming commands report the
    # missing dependency explicitly when they are invoked.
    RiverHalfSpaceTreesDetector = None  # type: ignore[assignment,misc]

__all__ = [
    "MahalanobisDetector",
    "PCADetector",
    "IForestDetector",
    "KNNDetector",
    "GMMDetector",
    "OCSVMDetector",
    "PyODECODDetector",
    "RiverHalfSpaceTreesDetector",
]
