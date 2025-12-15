from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, QSize, QDir
from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QTreeView,
    QFileSystemModel,
    QListWidget,
    QPushButton,
    QLabel,
    QListWidgetItem,
)


class StartupLayout(QWidget):
    """
    Encapsulates the Startup window layout (preferred current layout).
    Provides attributes used by logic in startup.py.
    """

    def __init__(self, parent: Optional[QWidget] = None, *, icon_size: QSize = QSize(128, 128)):
        super().__init__(parent)

        root = QHBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(self.splitter)

        # Left: directory tree
        self.fs_model = QFileSystemModel(self)
        self.fs_model.setRootPath("")
        self.fs_model.setFilter(
            QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot | QDir.Dirs | QDir.Drives
        )
        self.tree = QTreeView(self)
        self.tree.setModel(self.fs_model)
        self.tree.setHeaderHidden(False)

        # Middle: thumbnails and controls
        middle = QWidget(self)
        middle_layout = QVBoxLayout(middle)
        self.folder_label = QLabel("Select a folder to view images", middle)
        self.folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.image_list = QListWidget(middle)
        self.image_list.setResizeMode(QListWidget.Adjust)
        self.image_list.setViewMode(QListWidget.IconMode)
        self.image_list.setIconSize(icon_size)
        self.image_list.setSelectionMode(QListWidget.ExtendedSelection)

        # Buttons
        self.btn_select_all = QPushButton("Select All", middle)
        self.btn_select_none = QPushButton("Select None", middle)
        self.btn_load = QPushButton("Load Selected", middle)
        self.btn_cancel = QPushButton("Cancel", middle)

        middle_layout.addWidget(self.folder_label)
        middle_layout.addWidget(self.image_list)
        controls = QHBoxLayout()
        controls.addWidget(self.btn_select_all)
        controls.addWidget(self.btn_select_none)
        controls.addStretch(1)
        controls.addWidget(self.btn_cancel)
        controls.addWidget(self.btn_load)
        middle_layout.addLayout(controls)

        # Right panel placeholder where a preprocessing panel can be embedded
        self.right_panel = QWidget(self)
        self.right_panel_layout = QVBoxLayout(self.right_panel)
        self.right_panel_layout.addWidget(QLabel("Preprocessing", self.right_panel))

        # Add to splitter
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(middle)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 4)


class PreprocessingPanelLayout(QWidget):
    """
    Encapsulates the layout for the embedded preprocessing panel.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.header = QLabel("Preprocessing", self)
        layout.addWidget(self.header)

        self.preview = QLabel(self)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(400, 500)
        layout.addWidget(self.preview, 1)

        self.mask_list = QListWidget(self)
        self.mask_list.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self.mask_list, 1)

        row1 = QHBoxLayout()
        self.btn_select_background = QPushButton("Select Background", self)
        self.btn_isolate_foreground = QPushButton("Isolate Foreground", self)
        row1.addWidget(self.btn_select_background)
        row1.addWidget(self.btn_isolate_foreground)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_select_mask_as_bg = QPushButton("Select Mask as Background", self)
        self.btn_delete_mask = QPushButton("Delete Mask", self)
        row2.addWidget(self.btn_select_mask_as_bg)
        row2.addWidget(self.btn_delete_mask)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.btn_next = QPushButton("Next", self)
        row3.addStretch(1)
        row3.addWidget(self.btn_next)
        layout.addLayout(row3)


class PreprocessingWindowLayout(QWidget):
    """
    Encapsulates the layout for the standalone PreprocessingWindow.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        root = QHBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(self.splitter)

        # Left: directory tree
        self.fs_model = QFileSystemModel(self)
        self.fs_model.setRootPath("")
        self.fs_model.setFilter(
            QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot | QDir.Dirs | QDir.Drives
        )
        self.tree = QTreeView(self)
        self.tree.setModel(self.fs_model)
        self.tree.setHeaderHidden(False)

        # Middle: selected images list
        center = QWidget(self)
        center_layout = QVBoxLayout(center)
        self.selected_label = QLabel("Selected images", center)
        self.selected_list = QListWidget(center)
        self.selected_list.setResizeMode(QListWidget.Adjust)
        self.selected_list.setViewMode(QListWidget.IconMode)
        self.selected_list.setIconSize(QSize(96, 96))
        center_layout.addWidget(self.selected_label)
        center_layout.addWidget(self.selected_list, 1)
        self.btn_select_background = QPushButton("Select Background", center)
        self.btn_isolate_foreground = QPushButton("Isolate Foreground", center)
        center_btns = QHBoxLayout()
        center_btns.addWidget(self.btn_select_background)
        center_btns.addWidget(self.btn_isolate_foreground)
        center_layout.addLayout(center_btns)

        # Right: output panel
        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        self.preview_label = QLabel("Preview (overlay of 2 masks)", right)
        self.preview = QLabel(right)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(400, 400)
        right_layout.addWidget(self.preview_label)
        right_layout.addWidget(self.preview, 1)

        self.cluster_panel_label = QLabel("Clustering Panel", right)
        right_layout.addWidget(self.cluster_panel_label)
        self.mask_list = QListWidget(right)
        self.mask_list.setSelectionMode(QListWidget.SingleSelection)
        right_layout.addWidget(self.mask_list, 1)
        btn_row = QHBoxLayout()
        self.btn_select_mask_as_bg = QPushButton("Select Mask as Background", right)
        self.btn_delete_mask = QPushButton("Delete Mask", right)
        btn_row.addWidget(self.btn_select_mask_as_bg)
        btn_row.addWidget(self.btn_delete_mask)
        right_layout.addLayout(btn_row)

        nav_row = QHBoxLayout()
        self.btn_back = QPushButton("Back", right)
        self.btn_next = QPushButton("Next", right)
        nav_row.addWidget(self.btn_back)
        nav_row.addStretch(1)
        nav_row.addWidget(self.btn_next)
        right_layout.addLayout(nav_row)

        # Add to splitter
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(center)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 2)
