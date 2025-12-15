from __future__ import annotations

import os
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray
from sklearn.cluster import KMeans

from PyQt5.QtCore import Qt, QDir, QSize
from PyQt5.QtGui import QPixmap, QImage, QIcon
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QListWidgetItem,
    QFileDialog,
    QMessageBox,
)

from cmp_viewer.ui import PreprocessingWindowLayout, PreprocessingPanelLayout


IMAGE_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp"}


def _read_image_as_float(path: str) -> NDArray[np.float32]:
    """Read an image file into float32 in range [0,1] using Pillow (safer on Windows).

    We avoid loading pixel data via QPixmap/QImage here to prevent potential lifetime
    and plugin issues that can cause native crashes on some systems. Thumbnails for
    the UI can still use QPixmap; numerical processing uses Pillow → NumPy only.
    """
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        # Convert to single-channel luminance regardless of source mode
        im = im.convert("L")
        img = np.array(im, dtype=np.uint8)
    img = img.astype(np.float32)
    mx = float(img.max()) if img.size else 1.0
    if mx <= 0:
        mx = 1.0
    return img / mx


def _to_qpixmap_from_gray(gray: NDArray[np.float32]) -> QPixmap:
    g = np.clip(gray * 255.0, 0, 255).astype(np.uint8)
    h, w = g.shape
    qimg = QImage(g.data, w, h, w, QImage.Format.Format_Grayscale8)
    return QPixmap.fromImage(qimg.copy())


# Use shared mask utilities
try:
    # Prefer the common function from mask module
    from cmp_viewer.mask import overlay_masks as _overlay_masks
except Exception:
    # Fallback: local simple implementation if import fails
    def _overlay_masks(base: NDArray[np.float32], masks: List[NDArray[np.bool_]], colors: List[Tuple[int, int, int]] = None, alpha: float = 0.4) -> QPixmap:
        if colors is None:
            colors = [(255, 0, 0), (0, 255, 0)]
        h, w = base.shape
        base_u8 = np.clip(base * 255.0, 0, 255).astype(np.uint8)
        rgb = np.stack([base_u8, base_u8, base_u8], axis=-1).astype(np.float32)
        for m, c in zip(masks, colors):
            if m is None:
                continue
            m3 = np.stack([m, m, m], axis=-1)
            color_arr = np.array(c, dtype=np.float32)[None, None, :]
            rgb[m3] = (1 - alpha) * rgb[m3] + alpha * color_arr
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg.copy())


_SESSION_STATE = {
    "output_dir": None,
}


class PreprocessingWindow(QMainWindow):
    """
    Preprocessing UI:
    - Left: File system tree
    - Center: Selected images list with thumbnails
    - Right: Output preview (stack mean + overlay), mask selection, and actions
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CMP Viewer – Preprocessing")
        self.resize(1500, 900)

        # Use shared layout module
        layout_widget = PreprocessingWindowLayout(self)
        self.setCentralWidget(layout_widget)

        # Map widgets
        self.fs_model = layout_widget.fs_model
        self.tree = layout_widget.tree
        self.selected_list = layout_widget.selected_list
        self.preview = layout_widget.preview
        self.mask_list = layout_widget.mask_list
        self.btn_select_background = layout_widget.btn_select_background
        self.btn_isolate_foreground = layout_widget.btn_isolate_foreground
        self.btn_select_mask_as_bg = layout_widget.btn_select_mask_as_bg
        self.btn_delete_mask = layout_widget.btn_delete_mask
        self.btn_back = layout_widget.btn_back
        self.btn_next = layout_widget.btn_next

        # Initialize tree root and connect
        home_index = self.fs_model.index(QDir.homePath())
        if home_index.isValid():
            self.tree.setRootIndex(home_index)
        self.tree.clicked.connect(self.on_folder_clicked)

        # Data
        self.current_folder: str | None = None
        self.selected_files: List[str] = []
        self.images: List[NDArray[np.float32]] = []
        self.image_shape: Tuple[int, int] | None = None
        self.cluster_masks: List[NDArray[np.bool_]] | None = None
        self.bg_index: int | None = None

        # Wire
        self.btn_select_background.clicked.connect(self.on_select_background)
        self.btn_isolate_foreground.clicked.connect(self.on_isolate_foreground)
        self.btn_select_mask_as_bg.clicked.connect(self.on_select_mask_as_bg)
        self.btn_delete_mask.clicked.connect(self.on_delete_mask)
        self.btn_back.clicked.connect(self.on_back)
        self.btn_next.clicked.connect(self.on_next)

        # Keep a persistent reference to the next window to prevent premature GC
        self._next_window = None

    # ----- Loading/selection -----
    def open_images(self, files: List[str]):
        self.selected_files = [f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]
        self.populate_selected()
        self.load_images()

    def on_folder_clicked(self, index):
        path = self.fs_model.filePath(index)
        if not os.path.isdir(path):
            return
        self.current_folder = path
        # If user browses a new folder, allow quickly adding images from there
        self._populate_from_folder(path)

    def _populate_from_folder(self, folder: str):
        entries = sorted(os.listdir(folder))
        files = []
        for name in entries:
            full = os.path.join(folder, name)
            if os.path.isfile(full) and os.path.splitext(name)[1].lower() in IMAGE_EXTENSIONS:
                files.append(full)
        if files:
            self.selected_files = files
            self.populate_selected()
            self.load_images()

    def populate_selected(self):
        self.selected_list.clear()
        for path in self.selected_files:
            name = os.path.basename(path)
            item = QListWidgetItem(name)
            # icon
            try:
                pix = QPixmap(path)
                if not pix.isNull():
                    thumb = pix.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    item.setIcon(QIcon(thumb))
            except Exception:
                pass
            item.setToolTip(path)
            self.selected_list.addItem(item)

    def load_images(self):
        self.images = []
        for f in self.selected_files:
            try:
                img = _read_image_as_float(f)
                self.images.append(img)
            except Exception:
                continue
        if not self.images:
            self.image_shape = None
            self.preview.clear()
            return
        h, w = self.images[0].shape
        self.image_shape = (h, w)
        # Show stack mean as initial preview
        stack_mean = np.mean(np.stack(self.images, axis=0), axis=0)
        self.preview.setPixmap(_to_qpixmap_from_gray(stack_mean).scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # ----- Processing -----
    def on_select_background(self):
        if not self.images:
            QMessageBox.information(self, "No images", "Load or select images first.")
            return
        h, w = self.image_shape
        # Build per-pixel feature vector across images
        data = np.stack(self.images, axis=0)  # (N, H, W)
        data = data.reshape((data.shape[0], -1)).T  # (H*W, N)
        # KMeans with k=2
        km = KMeans(n_clusters=2, n_init=5, max_iter=100, tol=1e-3, random_state=42)
        labels = km.fit_predict(data)  # (H*W,)
        lbl_img = labels.reshape(h, w)
        mask0 = (lbl_img == 0)
        mask1 = (lbl_img == 1)
        self.cluster_masks = [mask0, mask1]

        # Populate mask list
        self.mask_list.clear()
        self.mask_list.addItem(f"Cluster 0 – area {mask0.sum()} px")
        self.mask_list.addItem(f"Cluster 1 – area {mask1.sum()} px")
        # Auto-suggest background as the larger area
        self.bg_index = 0 if mask0.sum() >= mask1.sum() else 1
        self.mask_list.setCurrentRow(self.bg_index)

        # Update overlay preview over stack mean
        stack_mean = np.mean(np.stack(self.images, axis=0), axis=0)
        pix = _overlay_masks(stack_mean, [mask0, mask1])
        self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # Update list text with coverage
        pct0 = 100.0 * mask0.mean()
        pct1 = 100.0 * mask1.mean()
        self.mask_list.item(0).setText(f"Cluster 0 – {pct0:.1f}% area")
        self.mask_list.item(1).setText(f"Cluster 1 – {pct1:.1f}% area")

    def on_isolate_foreground(self):
        if not self.images or not self.cluster_masks:
            QMessageBox.information(self, "Nothing to save", "Run 'Select Background' first.")
            return
        bg_id = self.bg_index if self.bg_index in (0, 1) else self.mask_list.currentRow()
        if bg_id not in (0, 1):
            QMessageBox.information(self, "Choose background", "Please select a cluster mask as background.")
            return
        fg_mask = ~self.cluster_masks[bg_id]
        h, w = self.image_shape
        # Choose output directory
        base_dir = os.path.dirname(self.selected_files[0]) if self.selected_files else os.getcwd()
        default_out = _SESSION_STATE.get("output_dir") or os.path.join(base_dir, "foreground_isolated")
        out_dir = QFileDialog.getExistingDirectory(self, "Choose output folder", default_out)
        if not out_dir:
            return
        if not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, "Cannot create folder", str(e))
                return
        # remember for session
        _SESSION_STATE["output_dir"] = out_dir

        # Save masked copies
        count = 0
        for src_path, img in zip(self.selected_files, self.images):
            name = os.path.basename(src_path)
            root, ext = os.path.splitext(name)
            out_path = os.path.join(out_dir, f"{root}_fg{ext or '.tif'}")
            try:
                # Apply mask: keep pixels under mask, zero background
                out = (img * fg_mask.astype(np.float32))
                # Save via Pillow
                from PIL import Image as PILImage
                out_u8 = np.clip(out * 255.0, 0, 255).astype(np.uint8)
                PILImage.fromarray(out_u8).save(out_path)
                count += 1
            except Exception as e:
                QMessageBox.warning(self, "Save error", f"Failed to save {out_path}: {e}")

        QMessageBox.information(self, "Done", f"Saved {count} foreground-isolated images to:\n{out_dir}")

    # --- clustering panel actions ---
    def on_select_mask_as_bg(self):
        row = self.mask_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select mask", "Please select a mask from the list.")
            return
        self.bg_index = row
        QMessageBox.information(self, "Background Selected", f"Cluster {row} set as background.")

    def on_delete_mask(self):
        row = self.mask_list.currentRow()
        if row < 0 or not self.cluster_masks:
            return
        if len(self.cluster_masks) <= 1:
            QMessageBox.information(self, "Cannot delete", "At least one mask must remain.")
            return
        del self.cluster_masks[row]
        self.mask_list.takeItem(row)
        # Rebuild overlay
        stack_mean = np.mean(np.stack(self.images, axis=0), axis=0)
        pix = _overlay_masks(stack_mean, self.cluster_masks)
        self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        # Reset bg index if necessary
        if self.bg_index == row:
            self.bg_index = 0

    # --- navigation ---
    def on_back(self):
        # Close and go back to Startup window
        try:
            from cmp_viewer.startup import StartupWindow
            w = StartupWindow()
            w.show()
            # Hold a reference so it isn't garbage collected
            self._next_window = w
        except Exception:
            pass
        self.close()

    def on_next(self):
        # After isolation, move to Clustering Window with output images
        out_dir = _SESSION_STATE.get("output_dir")
        if not out_dir or not os.path.isdir(out_dir):
            QMessageBox.information(self, "No foreground output", "Please run 'Isolate Foreground' first to proceed.")
            return
        # Collect images from output dir
        files = [os.path.join(out_dir, f) for f in sorted(os.listdir(out_dir))
                 if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]
        if not files:
            QMessageBox.information(self, "No images", "No isolated images found in the output folder.")
            return
        try:
            from cmp_viewer.clustering_window import ClusteringWindow
            win = ClusteringWindow()
            win.open_images(files)
            win.show()
            # Hold a reference so it isn't garbage collected
            self._next_window = win
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Navigation Error", f"Failed to open Clustering window: {e}")


class PreprocessingPanel(QWidget):
    """
    Preprocessing panel to be embedded in Startup window:
    - Accepts file list from Startup selection
    - Provides Select Background (KMeans k=2), shows overlay preview and mask list
    - Isolate Foreground to save masked copies
    - Optional Next navigation to Clustering
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Use shared panel layout
        layout_widget = PreprocessingPanelLayout(self)

        # Map widgets
        self.preview = layout_widget.preview
        self.mask_list = layout_widget.mask_list
        self.btn_select_background = layout_widget.btn_select_background
        self.btn_isolate_foreground = layout_widget.btn_isolate_foreground
        self.btn_select_mask_as_bg = layout_widget.btn_select_mask_as_bg
        self.btn_delete_mask = layout_widget.btn_delete_mask
        self.btn_next = layout_widget.btn_next

        # Data
        self.files: List[str] = []
        self.images: List[NDArray[np.float32]] = []
        self.image_shape: Tuple[int, int] | None = None
        self.cluster_masks: List[NDArray[np.bool_]] | None = None
        self.bg_index: int | None = None

        # Wire
        self.btn_select_background.clicked.connect(self.on_select_background)
        self.btn_isolate_foreground.clicked.connect(self.on_isolate_foreground)
        self.btn_select_mask_as_bg.clicked.connect(self.on_select_mask_as_bg)
        self.btn_delete_mask.clicked.connect(self.on_delete_mask)
        self.btn_next.clicked.connect(self.on_next)

        # Prevent GC of next window
        self._next_window = None

    def set_files(self, files: List[str]):
        self.files = [f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]
        self._load_images()

    def _load_images(self):
        self.images = []
        for f in self.files:
            try:
                self.images.append(_read_image_as_float(f))
            except Exception:
                continue
        if not self.images:
            self.image_shape = None
            self.preview.clear()
            self.mask_list.clear()
            self.cluster_masks = None
            return
        h, w = self.images[0].shape
        self.image_shape = (h, w)
        stack_mean = np.mean(np.stack(self.images, axis=0), axis=0)
        self.preview.setPixmap(_to_qpixmap_from_gray(stack_mean))

    def on_select_background(self):
        if not self.images:
            QMessageBox.information(self, "No images", "Load or select images first.")
            return
        h, w = self.image_shape
        data = np.stack(self.images, axis=0).reshape(len(self.images), -1).T
        km = KMeans(n_clusters=2, n_init=5, max_iter=100, tol=1e-3, random_state=42)
        labels = km.fit_predict(data)
        lbl_img = labels.reshape(h, w)
        mask0 = (lbl_img == 0)
        mask1 = (lbl_img == 1)
        self.cluster_masks = [mask0, mask1]

        self.mask_list.clear()
        self.mask_list.addItem(f"Cluster 0 – area {mask0.sum()} px")
        self.mask_list.addItem(f"Cluster 1 – area {mask1.sum()} px")
        self.bg_index = 0 if mask0.sum() >= mask1.sum() else 1
        self.mask_list.setCurrentRow(self.bg_index)

        stack_mean = np.mean(np.stack(self.images, axis=0), axis=0)
        pix = _overlay_masks(stack_mean, [mask0, mask1])
        self.preview.setPixmap(pix)

        pct0 = 100.0 * mask0.mean()
        pct1 = 100.0 * mask1.mean()
        self.mask_list.item(0).setText(f"Cluster 0 – {pct0:.1f}% area")
        self.mask_list.item(1).setText(f"Cluster 1 – {pct1:.1f}% area")

    def on_isolate_foreground(self):
        if not self.images or not self.cluster_masks:
            QMessageBox.information(self, "Nothing to save", "Run 'Select Background' first.")
            return
        bg_id = self.bg_index if self.bg_index in (0, 1) else self.mask_list.currentRow()
        if bg_id not in (0, 1):
            QMessageBox.information(self, "Choose background", "Please select a cluster mask as background.")
            return
        fg_mask = ~self.cluster_masks[bg_id]

        base_dir = os.path.dirname(self.files[0]) if self.files else os.getcwd()
        default_out = _SESSION_STATE.get("output_dir") or os.path.join(base_dir, "foreground_isolated")
        out_dir = QFileDialog.getExistingDirectory(self, "Choose output folder", default_out)
        if not out_dir:
            return
        if not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, "Cannot create folder", str(e))
                return
        _SESSION_STATE["output_dir"] = out_dir

        count = 0
        for src_path, img in zip(self.files, self.images):
            name = os.path.basename(src_path)
            root, ext = os.path.splitext(name)
            out_path = os.path.join(out_dir, f"{root}_fg{ext or '.tif'}")
            try:
                out = (img * fg_mask.astype(np.float32))
                from PIL import Image as PILImage
                out_u8 = np.clip(out * 255.0, 0, 255).astype(np.uint8)
                PILImage.fromarray(out_u8).save(out_path)
                count += 1
            except Exception as e:
                QMessageBox.warning(self, "Save error", f"Failed to save {out_path}: {e}")

        QMessageBox.information(self, "Done", f"Saved {count} foreground-isolated images to:\n{out_dir}")

    def on_select_mask_as_bg(self):
        row = self.mask_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select mask", "Please select a mask from the list.")
            return
        self.bg_index = row
        QMessageBox.information(self, "Background Selected", f"Cluster {row} set as background.")

    def on_delete_mask(self):
        row = self.mask_list.currentRow()
        if row < 0 or not self.cluster_masks:
            return
        if len(self.cluster_masks) <= 1:
            QMessageBox.information(self, "Cannot delete", "At least one mask must remain.")
            return
        del self.cluster_masks[row]
        self.mask_list.takeItem(row)
        if self.images and self.cluster_masks:
            stack_mean = np.mean(np.stack(self.images, axis=0), axis=0)
            pix = _overlay_masks(stack_mean, self.cluster_masks)
            self.preview.setPixmap(pix)
        if self.bg_index == row:
            self.bg_index = 0

    def on_next(self):
        out_dir = _SESSION_STATE.get("output_dir")
        if not out_dir or not os.path.isdir(out_dir):
            QMessageBox.information(self, "No foreground output", "Please run 'Isolate Foreground' first to proceed.")
            return
        files = [os.path.join(out_dir, f) for f in sorted(os.listdir(out_dir))
                 if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]
        if not files:
            QMessageBox.information(self, "No images", "No isolated images found in the output folder.")
            return
        try:
            from cmp_viewer.clustering_window import ClusteringWindow
            win = ClusteringWindow()
            win.open_images(files)
            win.show()
            self._next_window = win
        except Exception as e:
            QMessageBox.critical(self, "Navigation Error", f"Failed to open Clustering window: {e}")
