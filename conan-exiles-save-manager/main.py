"""
Conan Exiles Save Manager
A PySide6 application to manage selective backups of Conan Exiles saves.
Usage: python conan_save_manager.py
Requires PySide6 installed.
"""

import sys
import json
import shutil
import subprocess
import logging
from datetime import datetime
from pathlib import Path
import platform

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QStatusBar, QProgressDialog, QMessageBox, QInputDialog, QFileDialog,
    QToolButton, QHeaderView
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont, QIcon


class CopyWorker(QThread):
    """Handles copying files and folders in a separate thread, so the app doesn't freeze."""
    progress = Signal(int)
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, source_base, dest_base, paths, parent=None):
        """
        source_base: Where to copy from
        dest_base: Where to copy to
        paths: List of files/folders to copy (relative paths)
        """
        super().__init__(parent)
        self.source_base = source_base
        self.dest_base = dest_base
        self.paths = paths

    def run(self):
        """Does the actual copying work and sends progress updates."""
        try:
            total = len(self.paths)
            for i, rel_path in enumerate(self.paths):
                src = self.source_base / rel_path.rstrip('/')
                dst = self.dest_base / rel_path.rstrip('/')
                if not src.exists():
                    logging.warning(f"Source path does not exist: {src}")
                    continue
                try:
                    if src.is_dir():
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
                except Exception as e:
                    self.error.emit(f"Copy error for {rel_path}: {str(e)}")
                    self.finished.emit(False)
                    return
                self.progress.emit(int((i + 1) / total * 100))
            self.finished.emit(True)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)


class DeleteWorker(QThread):
    """Deletes a folder in a separate thread."""
    finished = Signal(bool)

    def __init__(self, path, parent=None):
        """
        path: Folder to delete
        """
        super().__init__(parent)
        self.path = path

    def run(self):
        """Deletes the folder and signals when done."""
        try:
            shutil.rmtree(self.path)
            self.finished.emit(True)
        except Exception as e:
            logging.error(f"Delete error: {str(e)}")
            self.finished.emit(False)


class LaunchWorker(QThread):
    """Launches Conan Exiles through Steam in a separate thread."""
    finished = Signal()

    def run(self):
        """Starts the game and waits for it to close."""
        try:
            p = subprocess.Popen(["steam", "steam://rungameid/440900"])
            p.wait()
        except Exception as e:
            logging.error(f"Launch error: {str(e)}")
        self.finished.emit()


def get_steam_path():
    """Tries to find where Steam is installed on this computer."""
    sys_plat = platform.system().lower()
    if sys_plat == 'windows':
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")
            value, _ = winreg.QueryValueEx(key, "SteamPath")
            winreg.CloseKey(key)
            return Path(value)
        except FileNotFoundError:
            pass
        except Exception as e:
            logging.error(f"Steam path detection error: {e}")
    elif sys_plat == 'linux':
        home = Path.home()
        candidates = [
            home / ".steam" / "steam",
            home / ".steam" / "debian-installation",
            home / ".local" / "share" / "Steam",
        ]
        for cand in candidates:
            if cand.exists():
                logging.info(f"Steam path found on Linux: {cand}")
                return cand
    return None


class MainWindow(QMainWindow):
    """
    The main window of the app. Handles all the UI and main logic for managing saves.
    """
    def __init__(self):
        """Sets up the main window and loads config, folders, and UI."""
        super().__init__()
        self.app = QApplication.instance()
        self.setWindowTitle("Conan Exiles Save Manager")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        self.app.setStyle("Fusion")
        self.app.setFont(QFont("Segoe UI", 10))

        self.dark_mode = False
        # self.toggle_mode()  # Moved after init_ui

        self.app_dir = Path(__file__).parent
        self.saved_dir = self.app_dir / "saved"
        self.config_path = self.app_dir / "config.json"
        self.logs_dir = self.app_dir / "logs"
        self.logs_path = self.logs_dir / "app.log"

        self.saved_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            filename=self.logs_path,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        logging.info("App started")

        self.game_saved = self.find_game_path()
        if not self.game_saved:
            sys.exit(1)

        self.config_paths = self.load_config()
        self.current_save = None

        self.init_ui()
        self.toggle_mode()  # Set initial light mode
        self.populate_tree()
        self.refresh_saves()
        self.update_buttons()

    def find_game_path(self):
        """Tries to find the Conan Exiles game folder automatically, or asks the user to pick it."""
        steam_path = get_steam_path()
        candidate = None
        if steam_path:
            candidate = steam_path / "steamapps" / "common" / "Conan Exiles" / "ConanSandbox"
            if candidate.exists():
                logging.info(f"Game path found: {candidate}")
                return candidate
        # Fallback to manual selection
        game_dir = QFileDialog.getExistingDirectory(
            self, "Select Conan Exiles ConanSandbox Folder"
        )
        if game_dir:
            candidate = Path(game_dir)
            if candidate.exists():
                logging.info(f"Manual game path: {candidate}")
                return candidate
        QMessageBox.critical(self, "Error", "Conan Exiles ConanSandbox folder not found. App cannot function.")
        return None

    def load_config(self):
        """Loads the list of files/folders to back up from config.json."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    paths = json.load(f)
                logging.info(f"Config loaded: {len(paths)} paths")
                return paths
            except Exception as e:
                logging.error(f"Config load error: {e}")
        return []

    def save_config(self):
        """Saves the current backup selections to config.json and updates the summary label."""
        self.config_paths = self.get_checked_paths()
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config_paths, f, indent=2)
            logging.info(f"Config saved: {len(self.config_paths)} paths")
        except Exception as e:
            logging.error(f"Config save error: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save config: {e}")

        # Update summary
        total_size = 0
        for rel_path in self.config_paths:
            p = self.game_saved / rel_path.rstrip('/')
            if p.exists():
                if p.is_dir():
                    for f in p.rglob("*"):
                        if f.is_file():
                            total_size += f.stat().st_size
                else:
                    total_size += p.stat().st_size
        mb = total_size / (1024 * 1024)
        self.summary_label.setText(f"Selected: {len(self.config_paths)} items totaling {mb:.1f} MB")
        self.update_buttons()

    def get_checked_paths(self):
        """Returns a list of all checked (selected) files/folders in the tree."""
        paths = []
        def recurse(item):
            if item.checkState(0) == Qt.Checked:
                rel = item.data(0, Qt.UserRole)
                if rel:
                    paths.append(rel)
            for i in range(item.childCount()):
                recurse(item.child(i))
        recurse(self.tree.invisibleRootItem())
        return paths

    def populate_tree(self):
        """Fills the tree view with files/folders from the game directory, showing which are selected."""
        self.tree.clear()
        config_set = set(self.config_paths)

        def add_items(parent, dir_path, rel=""):
            items = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for entry in items:
                if entry.is_dir():
                    new_rel = f"{rel}{entry.name}/" if rel else f"{entry.name}/"
                    item = QTreeWidgetItem(parent, [entry.name + "/"])
                    item.setCheckState(0, Qt.Checked if new_rel in config_set else Qt.Unchecked)
                    item.setData(0, Qt.UserRole, new_rel)
                    add_items(item, entry, new_rel)
                else:
                    new_rel = f"{rel}{entry.name}" if rel else entry.name
                    item = QTreeWidgetItem(parent, [entry.name])
                    item.setCheckState(0, Qt.Checked if new_rel in config_set else Qt.Unchecked)
                    item.setData(0, Qt.UserRole, new_rel)

        if self.game_saved.exists():
            add_items(self.tree, self.game_saved)
        else:
            self.tree.addTopLevelItem(QTreeWidgetItem(["Game folder not accessible"]))

    def init_ui(self):
        """Sets up the main layout, tabs, status bar, and theme toggle."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        self.saves_tab = self.init_saves_tab()
        self.config_tab = self.init_config_tab()
        self.tabs.addTab(self.saves_tab, "Saves")
        self.tabs.addTab(self.config_tab, "Configuration")
        layout.addWidget(self.tabs)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        mode_toggle = QToolButton()
        mode_toggle.setText("🌙")
        mode_toggle.setToolTip("Toggle Dark/Light Mode")
        mode_toggle.clicked.connect(self.toggle_mode)
        self.status_bar.addPermanentWidget(mode_toggle)

    def init_saves_tab(self):
        """Creates the Saves tab with all its buttons and the saves table."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Buttons - Row 1
        row1_layout = QHBoxLayout()
        self.backup_btn = QPushButton("💾 Backup Current Save")
        self.backup_btn.setToolTip("Backup selected files to a new save")
        self.backup_btn.clicked.connect(self.backup_save)
        row1_layout.addWidget(self.backup_btn)

        self.load_btn = QPushButton("📂 Load Selected Save")
        self.load_btn.setToolTip("Load the selected save into the game")
        self.load_btn.clicked.connect(self.load_save)
        row1_layout.addWidget(self.load_btn)

        self.launch_btn = QPushButton("🚀 Launch Game")
        self.launch_btn.setToolTip("Launch game and restore save on close")
        self.launch_btn.clicked.connect(self.launch_game)
        row1_layout.addWidget(self.launch_btn)

        self.create_btn = QPushButton("➕ Create New Save Slot")
        self.create_btn.setToolTip("Create a new save slot and backup current")
        self.create_btn.clicked.connect(self.create_new_save)
        row1_layout.addWidget(self.create_btn)

        layout.addLayout(row1_layout)

        # Buttons - Row 2
        row2_layout = QHBoxLayout()
        self.delete_btn = QPushButton("🗑️ Delete Selected Save")
        self.delete_btn.setToolTip("Delete the selected save folder")
        self.delete_btn.clicked.connect(self.delete_save)
        row2_layout.addWidget(self.delete_btn)

        self.change_mode_btn = QPushButton("🔄 Change Mode")
        self.change_mode_btn.setToolTip("Change the play mode for the selected save")
        self.change_mode_btn.clicked.connect(self.change_save_mode)
        row2_layout.addWidget(self.change_mode_btn)

        self.refresh_btn = QPushButton("🔄 Refresh List")
        self.refresh_btn.setToolTip("Refresh the saves list")
        self.refresh_btn.clicked.connect(self.refresh_saves)
        row2_layout.addWidget(self.refresh_btn)

        self.about_btn = QPushButton("ℹ️ About")
        self.about_btn.setToolTip("Show information about Conan Exiles")
        self.about_btn.clicked.connect(self.show_about)
        row2_layout.addWidget(self.about_btn)

        layout.addLayout(row2_layout)

        self.current_label = QLabel("Current Save: None")
        layout.addWidget(self.current_label)

        self.saves_table = QTableWidget()
        self.saves_table.setColumnCount(4)
        self.saves_table.setHorizontalHeaderLabels(["Name", "Date", "Size", "Mode"])
        # Make all columns stretch equally
        for i in range(4):
            self.saves_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        self.saves_table.cellClicked.connect(self.on_save_selected)
        layout.addWidget(self.saves_table)

        return tab

    def init_config_tab(self):
        """Creates the Configuration tab with the file/folder selection tree."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Select Files/Folders to Backup")
        self.tree.setToolTip("Check items to include in backups")
        layout.addWidget(self.tree)

        save_config_btn = QPushButton("💾 Save Config")
        save_config_btn.setToolTip("Save the current selections to config")
        save_config_btn.clicked.connect(self.save_config)
        layout.addWidget(save_config_btn)

        self.summary_label = QLabel("No config loaded")
        layout.addWidget(self.summary_label)

        return tab

    @Slot()
    def on_save_selected(self, row, col):
        """Called when a save is clicked in the table. Updates the current save selection."""
        item = self.saves_table.item(row, 0)
        if item:
            self.current_save = item.text()
            self.current_label.setText(f"Current Save: {self.current_save}")
            self.update_buttons()

    def update_buttons(self):
        """Enables or disables buttons based on what is selected/configured."""
        has_config = bool(self.config_paths)
        has_current = bool(self.current_save)
        self.backup_btn.setEnabled(has_config)
        self.load_btn.setEnabled(has_config and has_current)
        self.launch_btn.setEnabled(has_config and has_current)
        self.create_btn.setEnabled(has_config)
        self.delete_btn.setEnabled(has_current)

    def do_copy(self, source_base, dest_base, paths, title):
        """Starts a file copy operation and shows a progress dialog."""
        self.progress_dialog = QProgressDialog(title, "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        self.worker = CopyWorker(source_base, dest_base, paths, self)
        self.worker.progress.connect(self.progress_dialog.setValue)
        self.worker.finished.connect(lambda success: self.on_copy_finished(success, title))
        self.worker.error.connect(lambda msg: QMessageBox.warning(self, "Error", msg))
        self.worker.start()

        # Disable relevant buttons
        self.update_buttons()
        self.refresh_btn.setEnabled(False)

    def on_copy_finished(self, success, title):
        """Handles what happens after a copy operation finishes."""
        self.progress_dialog.close()
        self.refresh_btn.setEnabled(True)
        if success:
            logging.info(f"{title} completed successfully")
            self.refresh_saves()
            QMessageBox.information(self, "Success", f"{title} completed.")
        else:
            logging.warning(f"{title} failed")
        self.update_buttons()

    @Slot()
    def backup_save(self):
        """Backs up the selected files/folders to a new save slot."""
        if not self.config_paths:
            QMessageBox.warning(self, "Warning", "Please configure selections first.")
            return
        name, ok = QInputDialog.getText(self, "Backup Name", "Enter save name:")
        if ok and name.strip():
            name = name.strip()
            if (self.saved_dir / name).exists():
                QMessageBox.warning(self, "Warning", "Save name already exists.")
                return
            mode = self.choose_save_mode()
            if not mode:
                return
            backup_dir = self.saved_dir / name
            backup_dir.mkdir()
            self.save_metadata(backup_dir, mode)
            self.do_copy(self.game_saved, backup_dir, self.config_paths, f"Backing up to {name}...")

    @Slot()
    def load_save(self):
        """Loads the selected save into the game folder, overwriting current files."""
        if not self.current_save:
            QMessageBox.warning(self, "Warning", "Please select a save first.")
            return
        reply = QMessageBox.question(self, "Confirm", "Overwrite current game save?")
        if reply != QMessageBox.Yes:
            return
        backup_dir = self.saved_dir / self.current_save
        self.do_copy(backup_dir, self.game_saved, self.config_paths, f"Loading {self.current_save}...")

    @Slot()
    def launch_game(self):
        """Launches the game and restores the save after the game closes."""
        if not self.current_save:
            QMessageBox.warning(self, "Warning", "Please select a save first.")
            return
        self.launch_worker = LaunchWorker()
        self.launch_worker.finished.connect(lambda: self.restore_after_launch(self.current_save))
        self.launch_worker.start()

    def restore_after_launch(self, name):
        """Restores the save after the game is closed."""
        backup_dir = self.saved_dir / name
        self.do_copy(self.game_saved, backup_dir, self.config_paths, f"Restoring {name} after game...")

    @Slot()
    def create_new_save(self):
        """Creates a new save slot and backs up the current selection."""
        if not self.config_paths:
            QMessageBox.warning(self, "Warning", "Please configure selections first.")
            return
        name, ok = QInputDialog.getText(self, "New Save Slot", "Enter save name:")
        if ok and name.strip():
            name = name.strip()
            if (self.saved_dir / name).exists():
                QMessageBox.warning(self, "Warning", "Save name already exists.")
                return
            mode = self.choose_save_mode()
            if not mode:
                return
            backup_dir = self.saved_dir / name
            backup_dir.mkdir()
            self.save_metadata(backup_dir, mode)
            self.do_copy(self.game_saved, backup_dir, self.config_paths, f"Creating and backing up {name}...")

    def change_save_mode(self):
        """Lets the user change the play mode (Solo/Online) for a save slot."""
        if not self.current_save:
            QMessageBox.warning(self, "Warning", "Please select a save first.")
            return
        mode = self.choose_save_mode()
        if mode:
            save_dir = self.saved_dir / self.current_save
            self.save_metadata(save_dir, mode)
            self.refresh_saves()

    @Slot()
    def delete_save(self):
        """Deletes the currently selected save slot."""
        if not self.current_save:
            return
        reply = QMessageBox.question(self, "Confirm", f"Delete save '{self.current_save}'?")
        if reply != QMessageBox.Yes:
            return
        del_path = self.saved_dir / self.current_save
        self.del_worker = DeleteWorker(del_path, self)
        self.del_worker.finished.connect(lambda success: self.on_delete_finished(success))
        self.del_worker.start()

        # Temp disable
        self.delete_btn.setEnabled(False)

    def on_delete_finished(self, success):
        """Handles what happens after a save is deleted."""
        self.delete_btn.setEnabled(True)
        if success:
            logging.info(f"Deleted save: {self.current_save}")
            if self.current_save:
                self.current_save = None
                self.current_label.setText("Current Save: None")
            self.refresh_saves()
            self.update_buttons()
            QMessageBox.information(self, "Success", "Save deleted.")
        else:
            QMessageBox.warning(self, "Error", "Failed to delete save.")

    @Slot()
    def refresh_saves(self):
        """Refreshes the list of save slots shown in the table."""
        self.saves_table.setRowCount(0)
        if not self.saved_dir.exists():
            return
        for save_dir in sorted(self.saved_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if save_dir.is_dir():
                try:
                    stat = save_dir.stat()
                    date_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    total_size = 0
                    for f in save_dir.rglob("*"):
                        if f.is_file():
                            total_size += f.stat().st_size
                    size_str = f"{total_size / (1024 * 1024):.1f} MB"
                    mode = self.get_save_mode(save_dir)
                    row = self.saves_table.rowCount()
                    self.saves_table.insertRow(row)
                    self.saves_table.setItem(row, 0, QTableWidgetItem(save_dir.name))
                    self.saves_table.setItem(row, 1, QTableWidgetItem(date_str))
                    self.saves_table.setItem(row, 2, QTableWidgetItem(size_str))
                    self.saves_table.setItem(row, 3, QTableWidgetItem(mode))
                except Exception as e:
                    logging.error(f"Error refreshing save {save_dir}: {e}")

    def get_save_mode(self, save_dir):
        """Reads the play mode (Solo/Online) from a save's metadata.json."""
        meta_file = save_dir / "metadata.json"
        if meta_file.exists():
            try:
                with open(meta_file) as f:
                    data = json.load(f)
                return data.get("mode", "Unknown")
            except:
                pass
        return "Unknown"

    def choose_save_mode(self):
        """Shows a dialog to pick Solo or Online play mode."""
        msg = QMessageBox()
        msg.setWindowTitle("Select Play Mode")
        msg.setText("What type of save is this?")
        solo_btn = msg.addButton("Solo Play", QMessageBox.AcceptRole)
        online_btn = msg.addButton("Online Play", QMessageBox.AcceptRole)
        msg.addButton("Cancel", QMessageBox.RejectRole)
        msg.exec()
        if msg.clickedButton() == solo_btn:
            return "Solo Play"
        elif msg.clickedButton() == online_btn:
            return "Online Play"
        return None

    def save_metadata(self, save_dir, mode):
        """Writes the play mode info to metadata.json in the save slot."""
        meta_file = save_dir / "metadata.json"
        data = {"mode": mode}
        try:
            with open(meta_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save metadata for {save_dir}: {e}")

    def show_about(self):
        """Shows an About dialog with info about the app and Conan Exiles."""
        about_text = """
        <h2>Conan Exiles Save Manager</h2>
        <p>A tool for managing Conan Exiles game saves.</p>
        
        <h3>About Conan Exiles</h3>
        <p>Conan Exiles is an open-world survival game developed by Funcom, 
        based on the works of Robert E. Howard. Players must survive in a 
        harsh world, build bases, craft items, and battle enemies in a 
        dark fantasy setting.</p>
        
        <p><b>Developer:</b> Funcom<br>
        <b>Release Year:</b> 2018<br>
        <b>Platforms:</b> PC, PlayStation, Xbox</p>
        
        <p>This save manager helps you backup, restore, and organize your 
        game progress safely.</p>
        """
        QMessageBox.about(self, "About Conan Exiles", about_text)

    def toggle_mode(self):
        """Switches between dark and light mode for the app."""
        self.dark_mode = not self.dark_mode
        qss = self.get_qss()
        self.app.setStyleSheet(qss)
        self.status_bar.showMessage("Theme toggled" if self.dark_mode else "Theme toggled", 2000)

    def get_qss(self):
        """Returns the style sheet for the current theme (dark or light)."""
        if self.dark_mode:
            return """
            QMainWindow { background-color: #2B2B2B; color: #E0E0E0; }
            QTabWidget::pane { border: 1px solid #444; background: #2B2B2B; }
            QTabBar::tab { background: #404040; color: #E0E0E0; padding: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #4DA6FF; color: white; }
            QPushButton { background-color: #404040; border: 1px solid #555; color: #E0E0E0; padding: 8px; border-radius: 3px; }
            QPushButton:hover { background-color: #4DA6FF; color: white; }
            QPushButton:disabled { background-color: #303030; color: #808080; }
            QTableWidget { background-color: #353535; color: #E0E0E0; gridline-color: #444; alternate-background-color: #3A3A3A; }
            QTableWidget::item:selected { background-color: #4DA6FF; color: white; }
            QTreeWidget { background-color: #353535; color: #E0E0E0; border: 1px solid #444; }
            QProgressBar { background-color: #404040; color: #E0E0E0; border: 1px solid #555; text-align: center; }
            QProgressBar::chunk { background-color: #4DA6FF; }
            QLabel { color: #E0E0E0; }
            QStatusBar { background-color: #2B2B2B; color: #E0E0E0; }
            QMessageBox { background-color: #2B2B2B; color: #E0E0E0; }
            QMessageBox QLabel { color: #E0E0E0; }
            QMessageBox QPushButton { background-color: #404040; border: 1px solid #555; color: #E0E0E0; padding: 5px; }
            QMessageBox QPushButton:hover { background-color: #4DA6FF; color: white; }
            """
        else:
            return """
            QMainWindow { background-color: #F5F5F5; color: #333; }
            QTabWidget::pane { border: 1px solid #ccc; background: #F5F5F5; }
            QTabBar::tab { background: #E0E0E0; color: #333; padding: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #007ACC; color: white; }
            QPushButton { background-color: #E0E0E0; border: 1px solid #ccc; color: #333; padding: 8px; border-radius: 3px; }
            QPushButton:hover { background-color: #007ACC; color: white; }
            QPushButton:disabled { background-color: #F0F0F0; color: #808080; }
            QTableWidget { background-color: white; color: #333; gridline-color: #ddd; alternate-background-color: #F9F9F9; }
            QTableWidget::item:selected { background-color: #007ACC; color: white; }
            QTreeWidget { background-color: white; color: #333; border: 1px solid #ccc; }
            QProgressBar { background-color: #E0E0E0; color: #333; border: 1px solid #ccc; text-align: center; }
            QProgressBar::chunk { background-color: #007ACC; }
            QLabel { color: #333; }
            QStatusBar { background-color: #F5F5F5; color: #333; }
            QMessageBox { background-color: #F5F5F5; color: #333; }
            QMessageBox QLabel { color: #333; }
            QMessageBox QPushButton { background-color: #E0E0E0; border: 1px solid #CCC; color: #333; padding: 5px; }
            QMessageBox QPushButton:hover { background-color: #007ACC; color: white; }
            """


if __name__ == "__main__":
    # Start the app
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.png"))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())