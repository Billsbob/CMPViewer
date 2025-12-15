from __future__ import annotations

import os
from typing import List

from PyQt5.QtCore import Qt, QDir, QSize
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QMessageBox,
    QListWidgetItem,
)

from cmp_viewer.ui import StartupLayout


IMAGE_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp"}


class StartupWindow(QMainWindow):
    """Startup UI: left panel for folder navigation, Middle Panel for image selection, and right panel shows images and masks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CMP Viewer – Select Images")
        self.resize(1500, 900)

        # Use shared layout module
        layout_widget = StartupLayout(self)
        self.setCentralWidget(layout_widget)

        # Map commonly used widgets for logic
        self.fs_model = layout_widget.fs_model
        self.tree = layout_widget.tree
        self.folder_label = layout_widget.folder_label
        self.image_list = layout_widget.image_list
        self.btn_select_all = layout_widget.btn_select_all
        self.btn_select_none = layout_widget.btn_select_none
        self.btn_load = layout_widget.btn_load
        self.btn_cancel = layout_widget.btn_cancel

        # Initialize tree root and connect
        home_index = self.fs_model.index(QDir.homePath())
        if home_index.isValid():
            self.tree.setRootIndex(home_index)
        self.tree.clicked.connect(self.on_folder_selected)

        # Right: Preprocessing panel (embedded)
        try:
            from cmp_viewer.preprocessing import PreprocessingPanel
            self.preprocessing_panel = PreprocessingPanel(self)
            layout_widget.right_panel_layout.addWidget(self.preprocessing_panel, 1)
            layout_widget.right_panel.setMinimumWidth(400)
        except Exception:
            self.preprocessing_panel = None

        # Apply name filters to show only images in the tree view, like before
        image_filters = f"Images ({','.join(IMAGE_EXTENSIONS)})"
        try:
            self.fs_model.setNameFilters([image_filters])
            self.fs_model.setNameFilterDisables(False)
        except Exception:
            pass

        # Wire up buttons
        self.btn_select_all.clicked.connect(self.select_all)
        self.btn_select_none.clicked.connect(self.select_none)
        self.btn_cancel.clicked.connect(self.close)
        self.btn_load.clicked.connect(self.load_selected)

        self.current_folder: str | None = None
        # Keep a persistent reference to the next window to prevent premature GC
        self._next_window = None

    def on_folder_selected(self, index):
        # Only react to directories
        path = self.fs_model.filePath(index)
        if not os.path.isdir(path):
            return
        self.current_folder = path
        self.folder_label.setText(path)
        self.populate_images(path)

    def populate_images(self, folder: str):
        self.image_list.clear()
        if not os.path.isdir(folder):
            return
        entries = sorted(os.listdir(folder))
        for name in entries:
            full = os.path.join(folder, name)
            if not os.path.isfile(full):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in IMAGE_EXTENSIONS:
                continue

            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)

            # Try to build an icon thumbnail
            icon = self._make_icon(full)
            if icon is not None:
                item.setIcon(icon)

            # Store full path in item data
            item.setData(Qt.UserRole, full)
            self.image_list.addItem(item)

    def _make_icon(self, path: str) -> QIcon | None:
        try:
            pix = QPixmap(path)
            if pix.isNull():
                return None
            thumb = pix.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            return QIcon(thumb)
        except Exception:
            return None

    def select_all(self):
        for i in range(self.image_list.count()):
            self.image_list.item(i).setCheckState(Qt.Checked)

    def select_none(self):
        for i in range(self.image_list.count()):
            self.image_list.item(i).setCheckState(Qt.Unchecked)

    def selected_files(self) -> List[str]:
        files: List[str] = []
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            if item.checkState() == Qt.Checked:
                path = item.data(Qt.UserRole)
                if isinstance(path, str):
                    files.append(path)
        return files

    def load_selected(self):
        files = self.selected_files()
        if not files:
            QMessageBox.information(self, "No Images Selected", "Please select one or more images to continue.")
            return

        # Populate the embedded Preprocessing panel instead of opening a new window
        if self.preprocessing_panel is not None:
            self.preprocessing_panel.set_files(files)
            self.preprocessing_panel.show()
        else:
            # Fallback: open legacy PreprocessingWindow if panel failed to construct
            try:
                from cmp_viewer.preprocessing import PreprocessingWindow
                pre = PreprocessingWindow()
                if hasattr(pre, "open_images"):
                    pre.open_images(files)
                pre.show()
                self._next_window = pre
                self.close()
            except Exception:
                try:
                    from cmp_viewer.ImageViewer import ImageViewerUi
                    viewer = ImageViewerUi()
                    if hasattr(viewer, "open_images"):
                        viewer.open_images(files)
                    viewer.show()
                    self._next_window = viewer
                    self.close()
                except Exception:
                    QMessageBox.critical(self, "Launch Error", "Failed to open the next window.")
