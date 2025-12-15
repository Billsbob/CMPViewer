from __future__ import annotations

from typing import List

from PyQt5.QtWidgets import QToolBar, QAction

from cmp_viewer.ImageViewer import ImageViewerUi


class AnalysisWindow(ImageViewerUi):
    """
    Analysis window that focuses on viewing cluster mask overlays and exporting stats.
    This subclasses the existing ImageViewerUi to reuse its masking/overlay/export features.
    Adds a Back action to return to the ClusteringWindow.
    """

    def __init__(self, starting_images_folder=None):
        super().__init__(starting_images_folder)
        self.setWindowTitle("CMP Viewer – Analysis")
        # Minimal navigation toolbar
        tb = QToolBar("Navigation", self)
        self.addToolBar(tb)
        act_back = QAction("Back", self)
        act_back.triggered.connect(self.on_back)
        tb.addAction(act_back)

    def open_images(self, filenames: List[str]):
        # Reuse base implementation
        super().open_images(filenames)

    def on_back(self):
        try:
            from cmp_viewer.clustering_window import ClusteringWindow
            w = ClusteringWindow()
            # If we currently have images open, pass them back
            if hasattr(self, "_rawImageNames") and self._rawImageNames:
                try:
                    w.open_images(self._rawImageNames)
                except Exception:
                    pass
            w.show()
        except Exception:
            pass
        self.close()
