from __future__ import annotations

import os
from typing import List

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QMessageBox
)

IMAGE_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp"}


class ClusteringWindow(QMainWindow):
    """
    Clustering window (skeleton).
    For now, it lists incoming images (typically foreground-isolated) and provides Back/Next navigation.
    Future: add advanced clustering controls here as needed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CMP Viewer – Clustering")
        self.resize(1100, 750)

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        left = QWidget(self)
        v = QVBoxLayout(left)
        v.addWidget(QLabel("Images for Clustering:"))
        self.image_list = QListWidget(left)
        self.image_list.setViewMode(QListWidget.IconMode)
        self.image_list.setIconSize(QSize(96, 96))
        v.addWidget(self.image_list, 1)

        right = QWidget(self)
        rv = QVBoxLayout(right)
        self.info_label = QLabel("Select images and proceed to Analysis for mask overlays and stats.")
        rv.addWidget(self.info_label)
        rv.addStretch(1)
        self.btn_back = QPushButton("Back", right)
        self.btn_next = QPushButton("Next", right)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_back)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_next)
        rv.addLayout(btn_row)

        layout.addWidget(left, 2)
        layout.addWidget(right, 1)

        self.files: List[str] = []
        self.btn_back.clicked.connect(self.on_back)
        self.btn_next.clicked.connect(self.on_next)

    def open_images(self, files: List[str]):
        self.files = [f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]
        self.image_list.clear()
        for f in self.files:
            item = QListWidgetItem(os.path.basename(f))
            try:
                pix = QPixmap(f)
                if not pix.isNull():
                    item.setIcon(QIcon(pix.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            except Exception:
                pass
            item.setToolTip(f)
            self.image_list.addItem(item)

    def on_back(self):
        try:
            from cmp_viewer.preprocessing import PreprocessingWindow
            w = PreprocessingWindow()
            if self.files:
                w.open_images(self.files)
            w.show()
        except Exception:
            pass
        self.close()

    def on_next(self):
        if not self.files:
            QMessageBox.information(self, "No images", "No images to analyze.")
            return
        try:
            from cmp_viewer.analysis_window import AnalysisWindow
            w = AnalysisWindow()
            w.open_images(self.files)
            w.show()
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Navigation Error", f"Failed to open Analysis window: {e}")
