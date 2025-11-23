# src/main.py
import sys
import os
import ctypes

# Add "src/" into Python's search path
# This is required for Embeddable Python to work
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from gui import OCRWindow

try:
    # Arbitrary unique string to group taskbar icons
    myappid = 'th1nhhdk.localaiocr.2.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

def load_stylesheet(app):
    # Load Nord theme from style.qss
    style_path = os.path.join(current_dir, "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r") as f:
            app.setStyleSheet(f.read())

def main():
    app = QApplication(sys.argv)

    # Load Theme
    load_stylesheet(app)

    # Set program icon
    icon_path = os.path.join(current_dir, "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = OCRWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()