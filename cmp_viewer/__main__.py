import sys

from PyQt5.QtWidgets import QApplication

from cmp_viewer.startup import StartupWindow

"""
This is the main entry point for the CMP Viewer application.

CMP Viewer is a tool for visualizing and analyzing multidimensional images.
It provides functionality for loading images, performing clustering operations,
and visualizing the results. The application uses PyQt5 for its graphical user interface.
"""

def main():
    """
    Main function that initializes and runs the CMP Viewer application.

    This function creates a QApplication instance, initializes the main
    ImageViewerUi window, displays it, and starts the application's main event loop.

    Returns:
        None: The function does not return; it exits the program when the application closes.
    """
    # Create QApplication instance (remember 1 per project)
    CMPViewer = QApplication(sys.argv)

    # Initialize and show the Startup UI first
    startup = StartupWindow()
    startup.show()

    # Execute the main loop (this will block until the application exits)
    sys.exit(CMPViewer.exec_())

if __name__ == '__main__':
    main()
