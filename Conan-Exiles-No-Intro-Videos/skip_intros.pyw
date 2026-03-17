import os
import configparser
import subprocess
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

# Configuration
PATH_CONFIG_FILE = "path.ini"
CONAN_EXILES_STEAM_ID = "440900"
KEYWORDS = {
    "bWaitForMoviesToComplete=True": "bWaitForMoviesToComplete=False",
    "bMoviesAreSkippable=True": "bMoviesAreSkippable=True",
    "+StartupMovies=StartupUE4": ";+StartupMovies=StartupUE4",
    "+StartupMovies=StartupNvidia": ";+StartupMovies=StartupNvidia",
    "+StartupMovies=CinematicIntroV2": ";+StartupMovies=CinematicIntroV2"
}

class ConfigEditorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Conan Exiles - Skip Intro Videos")
        self.setGeometry(300, 300, 600, 300)
        self.setWindowIcon(QIcon("icon.png"))  # Optional: Set an icon if available
        
        # Load previous path if available
        self.ini_path = self.load_ini_path()
        
        # Setup UI and style
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        # Layout setup
        main_layout = QVBoxLayout()

        # Header label
        self.header_label = QLabel("Conan Exiles - Skip Intro Videos")
        self.header_label.setObjectName("headerLabel")
        self.header_label.setAlignment(Qt.AlignCenter)  # Center the header text
        
        # Selected file path display
        self.path_display = QLabel(self.ini_path if self.ini_path else "No file selected")
        self.path_display.setObjectName("pathDisplay")
        self.path_display.setAlignment(Qt.AlignCenter)  # Center the path display text
        
        # Buttons
        self.browse_button = QPushButton("Browse for DefaultGame.ini")
        self.browse_button.clicked.connect(self.browse_file)

        self.modify_button = QPushButton("Apply Modifications")
        self.modify_button.clicked.connect(self.modify_ini_file)

        self.launch_button = QPushButton("Launch Conan Exiles")
        self.launch_button.clicked.connect(self.launch_conan_exiles)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.browse_button)
        button_layout.addWidget(self.modify_button)
        button_layout.addWidget(self.launch_button)

        # Add widgets to main layout
        main_layout.addWidget(self.header_label)
        main_layout.addWidget(self.path_display)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def apply_styles(self):
        """Apply QSS styles for a modern look."""
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: Arial, sans-serif;
                font-size: 14px;
            }
            #headerLabel {
                font-size: 18px;
                font-weight: bold;
                color: #ffd700;
                padding: 10px;
            }
            #pathDisplay {
                border: 1px solid #444;
                padding: 10px;
                background-color: #3b3b3b;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #5a9;
                color: #fff;
                padding: 10px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #47a;
            }
            QPushButton:pressed {
                background-color: #3c8;
            }
        """)

    def load_ini_path(self):
        """Load the path from path.ini if it exists."""
        if os.path.exists(PATH_CONFIG_FILE):
            config = configparser.ConfigParser()
            config.read(PATH_CONFIG_FILE)
            return config.get("Paths", "DefaultGame.ini", fallback=None)
        return None

    def save_ini_path(self, path):
        """Save the selected path to path.ini."""
        config = configparser.ConfigParser()
        config["Paths"] = {"DefaultGame.ini": path}
        with open(PATH_CONFIG_FILE, "w") as config_file:
            config.write(config_file)
        
    def browse_file(self):
        """Browse for the DefaultGame.ini file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select DefaultGame.ini file", "", "INI Files (*.ini)")
        if file_path:
            self.ini_path = file_path
            self.path_display.setText(self.ini_path)
            self.save_ini_path(self.ini_path)

    def modify_ini_file(self):
        """Modify the appropriate lines in the DefaultGame.ini file."""
        if not self.ini_path or not os.path.exists(self.ini_path):
            QMessageBox.critical(self, "Error", "No valid DefaultGame.ini file selected.")
            return
        
        try:
            with open(self.ini_path, "r") as file:
                lines = file.readlines()
            
            # Apply modifications
            modified = False
            for i, line in enumerate(lines):
                for target, replacement in KEYWORDS.items():
                    if line.strip().startswith(target):
                        lines[i] = line.replace(target, replacement)
                        modified = True
            
            # Save changes if any modifications were made
            if modified:
                with open(self.ini_path, "w") as file:
                    file.writelines(lines)
                QMessageBox.information(self, "Success", "Modifications applied successfully!")
            else:
                QMessageBox.information(self, "Info", "No matching lines found to modify.")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while modifying the file: {e}")

    def launch_conan_exiles(self):
        """Launch Conan Exiles through Steam."""
        try:
            subprocess.run(["start", f"steam://rungameid/{CONAN_EXILES_STEAM_ID}"], check=True, shell=True)
            QMessageBox.information(self, "Launch", "Conan Exiles launched successfully.")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Error", f"Failed to launch Conan Exiles: {e}")

if __name__ == "__main__":
    app = QApplication([])
    window = ConfigEditorApp()
    window.show()
    app.exec()
