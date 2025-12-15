import os
import re
import csv
import cv2
import numpy as np
from numpy.typing import NDArray
from typing import Dict, Tuple
from PyQt5.QtGui import QImage, QColor, QPixmap
from PyQt5.QtCore import Qt
from PIL import Image
from cmp_viewer import utils

"""
Mask management, overlay creation, and export functions.
"""


def generate_masks(labels: NDArray[int], n_clusters: int) -> Dict[int, Tuple[NDArray[bool], QColor]]:
    """
    Generate binary masks and assign a unique color for each cluster.

    This method creates a binary mask for each unique cluster label and assigns
    a visually distinct color to each cluster using a perceptually-based approach.

    Args:
        labels (NDArray[int]): Array of cluster labels for each pixel.
        n_clusters (int): Number of clusters (may be different from actual unique labels).

    Returns:
        Dict[int, Tuple[NDArray[bool], QColor]]: Dictionary mapping cluster IDs to
                                                tuples of (binary mask, color).
    """
    masks = {}
    unique_labels = np.unique(labels)

    # Generate distinct colors for all unique labels
    colors = utils.generate_distinct_colors(len(unique_labels))

    for idx, cluster_id in enumerate(unique_labels):
        # Create binary mask for this cluster (True where label matches cluster_id)
        mask = (labels == cluster_id)

        # Assign a distinct color from our generated palette
        color = colors[idx]

        masks[cluster_id] = (mask, color)
    return masks


def create_mask_overlay(mask: NDArray[bool], color: QColor, opacity: int,
                           target_width: int = None, target_height: int = None) -> QImage:
    """
    Create a QImage overlay for a cluster mask with specified color and opacity.

    Args:
        mask (NDArray[bool]): Boolean mask for the cluster
        color (QColor): Color to use for the mask
        opacity (int): Opacity value (0-255)
        target_width (int, optional): Target width for resizing
        target_height (int, optional): Target height for resizing

    Returns:
        QImage: Transparent overlay with the mask colored
    """
    height, width = mask.shape

    # Resize mask if target dimensions are provided
    if target_width is not None and target_height is not None:
        mask_small = cv2.resize(mask.astype(np.uint8), (target_width, target_height),
                               interpolation=cv2.INTER_NEAREST).astype(bool)
        width, height = target_width, target_height
    else:
        mask_small = mask

    # Create transparent overlay
    overlay = QImage(width, height, QImage.Format_ARGB32)
    overlay.fill(Qt.transparent)

    # Apply color to mask
    # Note: QImage.Format_ARGB32 expects BGRA byte order in memory on little-endian systems.
    mask_data = np.zeros((height, width, 4), dtype=np.uint8)
    mask_data[mask_small, 0] = color.blue()   # B
    mask_data[mask_small, 1] = color.green()  # G
    mask_data[mask_small, 2] = color.red()    # R
    mask_data[mask_small, 3] = opacity        # A

    # Convert to QImage
    overlay_data = mask_data.tobytes()
    overlay = QImage(overlay_data, width, height, QImage.Format_ARGB32)

    return overlay


def export_cluster_mask(cluster_id: int, output_path: str, file_format: str = "tiff"):
    """
    Export a single cluster mask to a file.

    Args:
        cluster_id (int): ID of the cluster to export
        output_path (str): Path to save the mask
        file_format (str, optional): File format (tiff, png, etc.)

    Returns:
        bool: True if export was successful, False otherwise
    """
    if self.masks is None or cluster_id not in self.masks:
        return False

    mask, _ = self.masks[cluster_id]
    if mask is None:
        return False

    # Convert boolean mask to uint8 (0 or 255)
    mask_array = mask.astype(np.uint8) * 255
    mask_image = Image.fromarray(mask_array, mode='L')

    # Ensure output path has correct extension
    if not output_path.lower().endswith(f".{file_format.lower()}"):
        output_path = f"{output_path}.{file_format.lower()}"

    mask_image.save(output_path)
    return True


def overlay_masks(base: NDArray[np.float32], masks, colors=None, alpha: float = 0.4) -> QPixmap:
    """
    Create an RGB overlay pixmap showing boolean masks over a grayscale base image.

    Args:
        base: 2D float32 array in [0,1]
        masks: list of boolean 2D arrays matching base shape
        colors: list of (R,G,B) tuples, defaults to red/green for two masks
        alpha: blending factor [0..1]

    Returns:
        QPixmap with RGB overlay suitable for display in Qt labels.
    """
    import numpy as _np
    if colors is None:
        colors = [(255, 0, 0), (0, 255, 0)]
    h, w = base.shape
    base_u8 = _np.clip(base * 255.0, 0, 255).astype(_np.uint8)
    rgb = _np.stack([base_u8, base_u8, base_u8], axis=-1).astype(_np.float32)
    for m, c in zip(masks, colors):
        if m is None:
            continue
        m3 = _np.stack([m, m, m], axis=-1)
        color_arr = _np.array(c, dtype=_np.float32)[None, None, :]
        rgb[m3] = (1 - alpha) * rgb[m3] + alpha * color_arr
    rgb = _np.clip(rgb, 0, 255).astype(_np.uint8)
    qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())