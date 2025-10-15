# main.py
# This script is the main entry point for the application.
# Its sole responsibility is to initialize the QApplication and the main window.

import sys
from PyQt6.QtWidgets import QApplication
from app_ui import MainWindow

if __name__ == '__main__':
    # Create the application instance
    app = QApplication(sys.argv)

    # Create and show the main window
    window = MainWindow()
    window.show()

    # Start the application's event loop
    sys.exit(app.exec())
