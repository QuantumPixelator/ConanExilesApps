import os
import sys
import shutil
from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QRadioButton, QButtonGroup, QCheckBox, QPushButton, QFileDialog,
    QTableWidget, QTableWidgetItem, QMessageBox, QGroupBox, QGridLayout,
    QDialog, QDialogButtonBox, QHeaderView
)
from PySide6.QtWidgets import QComboBox
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt

import db_utils
import csv
import json
import time

APP_DIR = Path(__file__).resolve().parent

# Theme palettes
LIGHT = {
    'bg': '#f9fafb', 'fg': '#111827', 'muted': '#6b7280',
    'btn_bg': '#0f1724', 'btn_fg': '#ffffff', 'btn_disabled': '#94a3b8',
    'btn_hover': '#0b1220', 'btn_pressed': '#07101a', 'accent': '#2563eb',
    'input_bg': '#ffffff', 'border': '#e5e7eb',
    'group_border': '#e6e7eb', 'header_bg': '#f3f4f6', 'table_bg': '#ffffff',
    'alt_row': '#f8fafc', 'selection': '#e6f0ff'
}

DARK = {
    'bg': '#0b1020', 'fg': '#e6eef8', 'muted': '#9aa6bf',
    'btn_bg': '#1f2937', 'btn_fg': '#e6eef8', 'btn_disabled': '#374151',
    'btn_hover': '#273244', 'btn_pressed': '#1b2430', 'accent': '#60a5fa',
    'input_bg': '#071027', 'border': '#24303f',
    'group_border': '#172035', 'header_bg': '#0f1724', 'table_bg': '#071027',
    'alt_row': '#051226', 'selection': '#1f3a5a'
}

def build_stylesheet(pal):
    return f"""
    QWidget {{ background: {pal['bg']}; color: {pal['fg']}; font-family: 'Segoe UI', Arial; }}
    QLabel#title {{ font-size:18px; font-weight:600; color: {pal['fg']}; }}
    QPushButton {{ background: {pal['btn_bg']}; color: {pal['btn_fg']}; padding:6px 12px; border-radius:8px }}
    QPushButton:disabled {{ background: {pal['btn_disabled']}; color: {pal['muted']}; }}
    QLineEdit, QComboBox, QTableWidget, QPlainTextEdit {{ background: {pal['input_bg']}; color: {pal['fg']}; padding:6px; border:1px solid {pal['border']}; border-radius:6px }}
    QGroupBox {{ border: 1px solid {pal['group_border']}; border-radius:8px; margin-top:6px; padding:8px }}
    QHeaderView::section {{ background: {pal['header_bg']}; padding:6px; color: {pal['fg']}; }}
    QTableWidget {{ background: {pal['table_bg']}; gridline-color: {pal['border']}; }}
    QTableWidget::item {{ padding:6px; }}
    QTableView::item:selected, QTableWidget::item:selected {{ background: {pal['selection']}; color: {pal['fg']}; }}
    QTableWidget::item:hover {{ background: {pal['alt_row']}; }}
    QCheckBox {{ color: {pal['fg']}; }}
    QRadioButton {{ color: {pal['fg']}; }}
    QDialog {{ background: {pal['bg']}; color: {pal['fg']}; }}
    QComboBox QAbstractItemView {{ background: {pal['input_bg']}; color: {pal['fg']}; selection-background-color: {pal['header_bg']}; }}
    /* checkbox and radio indicators */
    QCheckBox::indicator, QRadioButton::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {pal['border']}; background: {pal['input_bg']}; }}
    QCheckBox::indicator:checked {{ background: {pal['accent']}; border-color: {pal['accent']}; }}
    QRadioButton::indicator {{ border-radius: 9px; }}
    QRadioButton::indicator:checked {{ background: {pal['accent']}; border-color: {pal['accent']}; }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {pal['accent']}; }}
    QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{ background: {pal['btn_disabled']}; border-color: {pal['btn_disabled']}; }}
    QCheckBox, QRadioButton {{ color: {pal['fg']}; }}
    /* focus ring for accessibility */
    QCheckBox:focus, QRadioButton:focus {{ outline: 2px solid {pal['accent']}; outline-offset: 2px; }}
    /* improve groupbox title visibility */
    QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px; color: {pal['fg']}; font-weight:600 }}
    /* Button hover/pressed states */
    QPushButton:hover {{ background: {pal['btn_hover']}; }}
    QPushButton:pressed {{ background: {pal['btn_pressed']}; }}
    """


class TransferApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Conan Exiles Ownership Transfer')
        self.setMinimumSize(900, 640)
        self.setup_ui()

    def setup_ui(self):
        font = QFont('Segoe UI', 10)
        self.setFont(font)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Header row: title left, theme toggle right
        header_row = QHBoxLayout()
        header = QLabel('Conan Exiles Ownership Transfer')
        header.setObjectName('title')
        header.setFont(QFont('Segoe UI Semibold', 18))
        header.setContentsMargins(6, 8, 6, 8)
        header_row.addWidget(header, 1)
        # theme toggle
        self.chk_dark = QCheckBox('Dark Mode')
        self.chk_dark.setToolTip('Toggle dark / light theme')
        self.chk_dark.toggled.connect(self.on_theme_toggled)
        header_row.addWidget(self.chk_dark, 0, Qt.AlignRight)
        layout.addLayout(header_row)

        # DB selection
        db_row = QHBoxLayout()
        db_row.addWidget(QLabel('Game DB:'))
        self.db_path = QLineEdit(str(Path.cwd() / 'game.db'))
        db_row.addWidget(self.db_path)
        btn_browse = QPushButton('Browse')
        btn_browse.clicked.connect(self.browse_db)
        db_row.addWidget(btn_browse)
        layout.addLayout(db_row)

        # Source/Target
        st_group = QGridLayout()

        st_group.addWidget(QLabel('Source:'), 0, 0)
        self.src_combo = QComboBox()
        st_group.addWidget(self.src_combo, 0, 1)
        self.src_combo.currentIndexChanged.connect(lambda: self.update_category_counts())
        btn_refresh_src = QPushButton('Refresh')
        btn_refresh_src.clicked.connect(lambda: self.populate_source_combo())
        st_group.addWidget(btn_refresh_src, 0, 2)

        st_group.addWidget(QLabel('Target:'), 1, 0)
        self.tgt_combo = QComboBox()
        st_group.addWidget(self.tgt_combo, 1, 1)
        btn_refresh_tgt = QPushButton('Refresh')
        btn_refresh_tgt.clicked.connect(lambda: self.populate_target_combo())
        st_group.addWidget(btn_refresh_tgt, 1, 2)

        group_box = QGroupBox('Transfer Settings')
        group_box.setLayout(st_group)
        group_box.setMinimumHeight(160)
        layout.addWidget(group_box)

        # when DB path changes, auto-load players/guilds
        btn_browse.clicked.connect(self.on_db_changed)
        # Categories
        cats = QHBoxLayout()
        cats.setSpacing(18)
        self.cb_items = QCheckBox('Items')
        self.cb_buildings = QCheckBox('Buildings')
        self.cb_thralls = QCheckBox('Thralls/Pets')
        self.cb_gameevents = QCheckBox('GameEvents (logs)')
        self.cb_all = QCheckBox('All')
        # default include game events for integrity
        self.cb_gameevents.setChecked(True)

        # per-object selection buttons
        self.btn_items_details = QPushButton('Details')
        self.btn_items_details.clicked.connect(self.show_items_details)
        self.btn_buildings_details = QPushButton('Details')
        self.btn_buildings_details.clicked.connect(self.show_buildings_details)
        self.btn_thralls_details = QPushButton('Details')
        self.btn_thralls_details.clicked.connect(self.show_thralls_details)

        # layout pieces
        items_box = QHBoxLayout()
        items_box.addWidget(self.cb_items)
        self.lbl_items_count = QLabel('(0)')
        items_box.addWidget(self.lbl_items_count)
        items_box.addWidget(self.btn_items_details)
        cats.addLayout(items_box)

        buildings_box = QHBoxLayout()
        buildings_box.addWidget(self.cb_buildings)
        self.lbl_buildings_count = QLabel('(0)')
        buildings_box.addWidget(self.lbl_buildings_count)
        buildings_box.addWidget(self.btn_buildings_details)
        cats.addLayout(buildings_box)

        thralls_box = QHBoxLayout()
        thralls_box.addWidget(self.cb_thralls)
        self.lbl_thralls_count = QLabel('(0)')
        thralls_box.addWidget(self.lbl_thralls_count)
        thralls_box.addWidget(self.btn_thralls_details)
        cats.addLayout(thralls_box)

        gameevents_box = QHBoxLayout()
        gameevents_box.addWidget(self.cb_gameevents)
        self.lbl_gameevents_count = QLabel('(0)')
        gameevents_box.addWidget(self.lbl_gameevents_count)
        cats.addLayout(gameevents_box)
        cats.addWidget(self.cb_all)
        layout.addLayout(cats)

        # keep 'All' checkbox in sync with individual category checkboxes
        self.cb_all.toggled.connect(self.on_all_toggled)
        for _cb in (self.cb_items, self.cb_buildings, self.cb_thralls, self.cb_gameevents):
            _cb.toggled.connect(self.on_category_toggled)
        
        self.cb_include_discovered = QCheckBox('Also update all owner-like columns discovered in DB (recommended)')
        self.cb_include_discovered.setChecked(True)
        layout.addWidget(self.cb_include_discovered)

        # Action buttons
        row = QHBoxLayout()
        row.setSpacing(10)
        self.btn_analyze = QPushButton('Analyze (Dry-run)')
        self.btn_analyze.clicked.connect(self.on_analyze)
        self.btn_transfer = QPushButton('Transfer')
        self.btn_transfer.clicked.connect(self.on_transfer)
        # Extra actions: Export audit CSV and Revert
        self.btn_export_audit = QPushButton('Export Audit CSV')
        self.btn_export_audit.clicked.connect(self.on_export_audit)
        self.btn_view_audit = QPushButton('View Audit')
        self.btn_view_audit.clicked.connect(self.on_view_audit)
        self.btn_revert = QPushButton('Revert Transfer')
        self.btn_revert.clicked.connect(self.on_revert_transfer)
        row.addWidget(self.btn_analyze)
        row.addWidget(self.btn_transfer)
        row.addWidget(self.btn_export_audit)
        row.addWidget(self.btn_view_audit)
        row.addWidget(self.btn_revert)
        layout.addLayout(row)

        # Results table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Category','Before','Transferred'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        layout.addWidget(self.table)

        self.setLayout(layout)

        # apply initial theme (light by default)
        self.current_theme = 'light'
        self.apply_theme('light')

    def browse_db(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select game.db', str(Path.cwd()), 'SQLite DB (*.db *.sqlite *.sqlite3);;All Files (*)')
        if path:
            self.db_path.setText(path)
            self.on_db_changed()

    def on_theme_toggled(self, checked: bool):
        self.apply_theme('dark' if checked else 'light')

    def apply_theme(self, which: str):
        pal = DARK if which == 'dark' else LIGHT
        css = build_stylesheet(pal)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(css)
        # keep state
        self.current_theme = which

    def on_all_toggled(self, checked: bool):
        # when user toggles 'All', set all individual category checkboxes to match
        for _cb in (self.cb_items, self.cb_buildings, self.cb_thralls, self.cb_gameevents):
            _cb.blockSignals(True)
            _cb.setChecked(checked)
            _cb.blockSignals(False)

    def on_category_toggled(self, checked: bool):
        # if all individual categories are checked, mark 'All' as checked; otherwise unset it
        all_checked = all(cb.isChecked() for cb in (self.cb_items, self.cb_buildings, self.cb_thralls, self.cb_gameevents))
        self.cb_all.blockSignals(True)
        self.cb_all.setChecked(all_checked)
        self.cb_all.blockSignals(False)

    def on_db_changed(self):
        db = self.db_path.text().strip()
        if not db or not os.path.exists(db):
            return
        # populate combos
        self.populate_source_combo()
        self.populate_target_combo()

    def update_category_counts(self):
        """Update the small count labels next to each category checkbox based on selected source."""
        db = self.db_path.text().strip()
        if not db or not os.path.exists(db):
            return
        source_id = self.get_selected_source_id()
        if source_id is None:
            return
        try:
            sim = db_utils.simulate_update_counts(db, source_id, ['all'], source_is_guild=False)
            items = sim.get('items', 0)
            blds = sim.get('buildings', 0)
            thralls = sim.get('thralls', 0)
            ge = sim.get('game_events_owner', 0)
            self.lbl_items_count.setText(f"({items})")
            self.lbl_buildings_count.setText(f"({blds})")
            self.lbl_thralls_count.setText(f"({thralls})")
            # show game_events as sum of owner+guild
            self.lbl_gameevents_count.setText(f"({ge})")
            # Gray-out logic: disable checkbox and details button when count is zero
            def apply_state(count, checkbox, details_btn, label):
                enabled = bool(count)
                # if zero, disable and uncheck; otherwise enable
                checkbox.setEnabled(enabled)
                if not enabled:
                    try:
                        checkbox.setChecked(False)
                    except Exception:
                        pass
                if details_btn:
                    details_btn.setEnabled(enabled)
                # label muted when zero
                if enabled:
                    label.setStyleSheet('')
                else:
                    label.setStyleSheet('color: #94a3b8')

            apply_state(items, self.cb_items, getattr(self, 'btn_items_details', None), self.lbl_items_count)
            apply_state(blds, self.cb_buildings, getattr(self, 'btn_buildings_details', None), self.lbl_buildings_count)
            apply_state(thralls, self.cb_thralls, getattr(self, 'btn_thralls_details', None), self.lbl_thralls_count)
            apply_state(ge, self.cb_gameevents, None, self.lbl_gameevents_count)
        except Exception:
            pass

    def populate_source_combo(self):
        db = self.db_path.text().strip()
        if not db or not os.path.exists(db):
            return
        try:
            self.src_combo.clear()
            chars = db_utils.list_characters(db)
            for c in chars:
                display = f"{c.get('id')} - {c.get('char_name')}"
                self.src_combo.addItem(display, c.get('id'))
        except Exception as e:
            QMessageBox.warning(self, 'Warning', f'Failed to load source list: {e}')
        # update counts for the newly populated selection
        try:
            self.update_category_counts()
        except Exception:
            pass

    def populate_target_combo(self):
        db = self.db_path.text().strip()
        if not db or not os.path.exists(db):
            return
        try:
            self.tgt_combo.clear()
            chars = db_utils.list_characters(db)
            for c in chars:
                display = f"{c.get('id')} - {c.get('char_name')}"
                self.tgt_combo.addItem(display, c.get('id'))
        except Exception as e:
            QMessageBox.warning(self, 'Warning', f'Failed to load target list: {e}')

    def get_selected_source_id(self):
        try:
            return int(self.src_combo.currentData())
        except Exception:
            return None

    def get_selected_target_id(self):
        try:
            return int(self.tgt_combo.currentData())
        except Exception:
            return None

    def _selected_categories(self) -> List[str]:
        if self.cb_all.isChecked():
            return ['all']
        cats = []
        if self.cb_items.isChecked(): cats.append('items')
        if self.cb_buildings.isChecked(): cats.append('buildings')
        if self.cb_thralls.isChecked(): cats.append('thralls')
        if self.cb_gameevents.isChecked(): cats.append('game_events')
        return cats

    def _load_xref(self):
        # try to find workspace item_xref file (one level up from this app folder)
        ws = Path(__file__).resolve().parents[1]
        candidate = ws / 'item_xref'
        if candidate.exists():
            return db_utils.load_item_xref_file(str(candidate))
        return {}

    def _show_selection_dialog(self, rows, id_key, title):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumSize(700, 400)
        v = QVBoxLayout(dlg)
        tbl = QTableWidget(0, 4)
        tbl.setHorizontalHeaderLabels(['Select', 'ID', 'Template', 'Info'])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for r in rows:
            i = tbl.rowCount(); tbl.insertRow(i)
            chk = QTableWidgetItem('')
            chk.setFlags(chk.flags() | Qt.ItemIsUserCheckable)
            chk.setCheckState(Qt.Unchecked)
            tbl.setItem(i, 0, chk)
            tbl.setItem(i, 1, QTableWidgetItem(str(r.get(id_key))))
            name = r.get('template_name') or str(r.get('template_id'))
            tbl.setItem(i, 2, QTableWidgetItem(name))
            info = ''
            if r.get('class'):
                info = str(r.get('class'))
            elif r.get('inv_type') is not None:
                info = f"inv_type={r.get('inv_type')}"
            tbl.setItem(i, 3, QTableWidgetItem(info))

        v.addWidget(tbl)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        v.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return []
        # collect checked ids
        selected = []
        for r in range(tbl.rowCount()):
            it = tbl.item(r, 0)
            if it.checkState() == Qt.Checked:
                selected.append(int(tbl.item(r, 1).text()))
        return selected

    def show_items_details(self):
        db = self.db_path.text().strip()
        if not db or not os.path.exists(db):
            QMessageBox.critical(self, 'Error', 'Please select a valid game.db file.')
            return
        source_id = self.get_selected_source_id()
        if source_id is None:
            QMessageBox.critical(self, 'Error', 'Select a valid source.')
            return
        xref = self._load_xref()
        rows = db_utils.list_items_for_owner(db, source_id, xref, owner_is_guild=False)
        if not rows:
            QMessageBox.information(self, 'No Items', 'No items found for this owner.')
            return
        ids = self._show_selection_dialog(rows, 'item_id', 'Select Items to Transfer')
        self.selected_item_ids = ids

    def show_buildings_details(self):
        db = self.db_path.text().strip()
        if not db or not os.path.exists(db):
            QMessageBox.critical(self, 'Error', 'Please select a valid game.db file.')
            return
        source_id = self.get_selected_source_id()
        if source_id is None:
            QMessageBox.critical(self, 'Error', 'Select a valid source.')
            return
        xref = self._load_xref()
        rows = db_utils.list_buildings_for_owner(db, source_id, xref, owner_is_guild=False)
        if not rows:
            QMessageBox.information(self, 'No Buildings', 'No buildings found for this owner.')
            return
        ids = self._show_selection_dialog(rows, 'object_id', 'Select Buildings to Transfer')
        self.selected_building_object_ids = ids

    def show_thralls_details(self):
        db = self.db_path.text().strip()
        if not db or not os.path.exists(db):
            QMessageBox.critical(self, 'Error', 'Please select a valid game.db file.')
            return
        source_id = self.get_selected_source_id()
        if source_id is None:
            QMessageBox.critical(self, 'Error', 'Select a valid source.')
            return
        rows = db_utils.list_thralls_for_owner(db, source_id, owner_is_guild=False)
        if not rows:
            QMessageBox.information(self, 'No Thralls', 'No placed followers (thralls/pets) found for this owner.')
            return

        # Build a dialog table specifically for placed followers (actors)
        dlg = QDialog(self)
        dlg.setWindowTitle('Select Placed Followers to Transfer')
        dlg.setMinimumSize(700, 420)
        v = QVBoxLayout(dlg)
        tbl = QTableWidget(0, 5)
        tbl.setHorizontalHeaderLabels(['Select', 'Actor ID', 'Template', 'Class', 'Coords'])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for r in rows:
            i = tbl.rowCount(); tbl.insertRow(i)
            chk = QTableWidgetItem('')
            chk.setFlags(chk.flags() | Qt.ItemIsUserCheckable)
            chk.setCheckState(Qt.Unchecked)
            tbl.setItem(i, 0, chk)
            actor_id = str(r.get('follower_id', ''))
            tbl.setItem(i, 1, QTableWidgetItem(actor_id))
            tbl.setItem(i, 2, QTableWidgetItem(str(r.get('template_name', ''))))
            tbl.setItem(i, 3, QTableWidgetItem(str(r.get('class', ''))))
            tbl.setItem(i, 4, QTableWidgetItem(str(r.get('coords', ''))))

        v.addWidget(tbl)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        v.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return
        selected = []
        for r in range(tbl.rowCount()):
            it = tbl.item(r, 0)
            if it and it.checkState() == Qt.Checked:
                selected.append(int(tbl.item(r, 1).text()))
        self.selected_thrall_ids = selected

    def on_export_audit(self):
        # open save dialog to export CSV (copy existing audit to chosen location)
        audit = APP_DIR / 'transfers_audit.csv'
        if not audit.exists():
            QMessageBox.information(self, 'No Audit', 'No audit file found to export.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export Audit CSV', str(Path.home() / 'transfers_audit.csv'), 'CSV Files (*.csv)')
        if not path:
            return
        try:
            shutil.copy2(str(audit), path)
            QMessageBox.information(self, 'Exported', f'Audit CSV exported to: {path}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to export audit: {e}')

    # guild-related UI removed

    def _load_audit_records(self):
        audit = APP_DIR / 'transfers_audit.csv'
        if not audit.exists():
            return []
        recs = []
        try:
            with open(audit, 'r', encoding='utf-8') as f:
                rdr = csv.DictReader(f)
                for r in rdr:
                    # some audit files use 'changed_json' as the column name
                    if 'changed_json' in r and r.get('changed_json'):
                        try:
                            r['changed'] = json.loads(r['changed_json'])
                        except Exception:
                            r['changed'] = {}
                    # try to decode JSON-like fields
                    for k in ('categories', 'item_ids', 'building_object_ids', 'thrall_ids', 'before_source', 'after_source', 'before_target', 'after_target'):
                        if k in r and r[k]:
                            try:
                                r[k] = json.loads(r[k])
                            except Exception:
                                pass
                    # if a legacy 'changed' column exists and is JSON, decode it
                    if 'changed' in r and isinstance(r['changed'], str) and r['changed']:
                        try:
                            r['changed'] = json.loads(r['changed'])
                        except Exception:
                            pass
                    recs.append(r)
        except Exception:
            return []
        return recs

    def on_view_audit(self):
        recs = self._load_audit_records()
        if not recs:
            QMessageBox.information(self, 'No Audit', 'No audit records found.')
            return
        dlg = QDialog(self)
        dlg.setWindowTitle('Transfers Audit')
        dlg.setMinimumSize(1200, 520)
        v = QVBoxLayout(dlg)
        # Add columns for before/after counts and deltas
        columns = [
            'Timestamp','DB Path','Source','Target','Categories',
            'Items Δ','Buildings Δ','Thralls Δ',
            'Before Src','After Src','Before Tgt','After Tgt',
            'Changed'
        ]
        tbl = QTableWidget(0, len(columns))
        tbl.setHorizontalHeaderLabels(columns)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for r in recs:
            i = tbl.rowCount(); tbl.insertRow(i)
            ts = r.get('timestamp') or r.get('time') or ''
            try:
                ts = int(ts)
            except Exception:
                pass
            tbl.setItem(i, 0, QTableWidgetItem(str(ts)))
            tbl.setItem(i, 1, QTableWidgetItem(r.get('db_path', '')))
            tbl.setItem(i, 2, QTableWidgetItem(str(r.get('source_id', ''))))
            tbl.setItem(i, 3, QTableWidgetItem(str(r.get('target_id', ''))))
            cats = r.get('categories')
            tbl.setItem(i, 4, QTableWidgetItem(','.join(cats) if isinstance(cats, list) else str(cats)))
            # Compute deltas for items, buildings, thralls
            def safe_get(d, k):
                return d.get(k, 0) if isinstance(d, dict) else 0
            before_src = r.get('before_source', {})
            after_src = r.get('after_source', {})
            before_tgt = r.get('before_target', {})
            after_tgt = r.get('after_target', {})
            items_delta = safe_get(after_tgt, 'items') - safe_get(before_tgt, 'items')
            bld_delta = safe_get(after_tgt, 'buildings') - safe_get(before_tgt, 'buildings')
            thrall_delta = safe_get(after_tgt, 'thralls') - safe_get(before_tgt, 'thralls')
            tbl.setItem(i, 5, QTableWidgetItem(str(items_delta)))
            tbl.setItem(i, 6, QTableWidgetItem(str(bld_delta)))
            tbl.setItem(i, 7, QTableWidgetItem(str(thrall_delta)))
            # Show before/after counts as JSON
            import json
            tbl.setItem(i, 8, QTableWidgetItem(json.dumps(before_src, ensure_ascii=False)))
            tbl.setItem(i, 9, QTableWidgetItem(json.dumps(after_src, ensure_ascii=False)))
            tbl.setItem(i, 10, QTableWidgetItem(json.dumps(before_tgt, ensure_ascii=False)))
            tbl.setItem(i, 11, QTableWidgetItem(json.dumps(after_tgt, ensure_ascii=False)))
            changed = r.get('changed')
            if isinstance(changed, dict):
                changed_s = ', '.join(f"{k}:{v}" for k, v in changed.items())
            else:
                changed_s = str(changed)
            tbl.setItem(i, 12, QTableWidgetItem(changed_s))

        # autosize columns to contents, keep last column flexible
        for c in range(tbl.columnCount() - 1):
            tbl.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(tbl.columnCount() - 1, QHeaderView.Stretch)
        v.addWidget(tbl)
        btns = QDialogButtonBox()
        refresh = QPushButton('Refresh')
        refresh.clicked.connect(lambda: dlg.done(2))
        close = QPushButton('Close')
        close.clicked.connect(dlg.accept)
        h = QHBoxLayout()
        h.addWidget(refresh); h.addWidget(close)
        v.addLayout(h)
        # loop allow refresh: if user presses Refresh, re-open dialog with reloaded data
        res = dlg.exec()
        if res == 2:
            # user clicked Refresh, reopen
            self.on_view_audit()

    def on_revert_transfer(self):
        # Choose a transferred DB file to revert
        path, _ = QFileDialog.getOpenFileName(self, 'Select transferred DB to revert', str(APP_DIR), 'DB Files (*.db);;All Files (*)')
        if not path:
            return
        ok = QMessageBox.question(self, 'Confirm Revert', f'Revert the selected transferred DB: {Path(path).name}? This will overwrite the file with its pre-transfer backup.')
        if ok != QMessageBox.StandardButton.Yes:
            return
        success, msg = db_utils.revert_transfer(path)
        if success:
            QMessageBox.information(self, 'Reverted', msg)
        else:
            QMessageBox.critical(self, 'Revert Failed', msg)

    def on_analyze(self):
        db = self.db_path.text().strip()
        if not db or not os.path.exists(db):
            QMessageBox.critical(self, 'Error', 'Please select a valid game.db file.')
            return
        source_id = self.get_selected_source_id()
        if source_id is None:
            QMessageBox.critical(self, 'Error', 'Select a valid source.')
            return
        cats = self._selected_categories()
        if not cats:
            QMessageBox.critical(self, 'Error', 'Select one or more categories to analyze.')
            return

        # Copy DB for safe dry-run analysis (not strictly necessary, just safe)
        working = Path(APP_DIR) / 'game_copy_for_analysis.db'
        try:
            shutil.copy2(db, working)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Could not copy DB: {e}')
            return

        sim = db_utils.simulate_update_counts(str(working), source_id, cats, source_is_guild=False)
        # populate table
        self.table.setRowCount(0)
        rows = [
            ('Items (inventory)', sim.get('item_inventory', 0)),
            ('Item properties', sim.get('item_properties', 0)),
            ('Buildings', sim.get('buildings', 0)),
            ('Thralls/Pets', sim.get('thralls', 0)),
            ('GameEvents owner', sim.get('game_events_owner', 0)),
        ]
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(r[0]))
            self.table.setItem(i, 1, QTableWidgetItem(str(r[1])))
            self.table.setItem(i, 2, QTableWidgetItem('0'))

        QMessageBox.information(self, 'Dry-run Complete', 'Analysis complete. Review counts before transferring.')

    def show_pretransfer_summary(self, counts: dict, selected_items: int, selected_buildings: int, selected_thralls: int) -> bool:
        dlg = QDialog(self)
        dlg.setWindowTitle('Pre-Transfer Summary')
        dlg.setMinimumSize(520, 320)
        v = QVBoxLayout(dlg)

        lbl = QLabel('Summary of items that will be affected')
        lbl.setStyleSheet('font-weight:600; padding-bottom:6px;')
        v.addWidget(lbl)

        tbl = QTableWidget(0, 2)
        tbl.setHorizontalHeaderLabels(['Category','Count'])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for k in ('item_inventory','item_properties','buildings','thralls','game_events_owner'):
            i = tbl.rowCount(); tbl.insertRow(i)
            tbl.setItem(i, 0, QTableWidgetItem(k.replace('_',' ').title()))
            tbl.setItem(i, 1, QTableWidgetItem(str(counts.get(k,0))))
        v.addWidget(tbl)

        details = QLabel(f'Selected subset: {selected_items} items, {selected_buildings} buildings, {selected_thralls} thralls')
        details.setStyleSheet('color: #6b7280; padding-top:8px')
        v.addWidget(details)

        note = QLabel('Note: Discovered owner-like columns may also be updated (optional).')
        note.setWordWrap(True)
        v.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        v.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        return dlg.exec() == QDialog.Accepted

    def on_transfer(self):
        db = self.db_path.text().strip()
        if not db or not os.path.exists(db):
            QMessageBox.critical(self, 'Error', 'Please select a valid game.db file.')
            return
        source_id = self.get_selected_source_id()
        target_id = self.get_selected_target_id()
        if source_id is None or target_id is None:
            QMessageBox.critical(self, 'Error', 'Select valid source and target.')
            return
        cats = self._selected_categories()
        if not cats:
            QMessageBox.critical(self, 'Error', 'Select one or more categories to transfer.')
            return

        # Ask user if they want to back up the DB
        # Ask user if they want to back up the DB (with prominent warning)
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle('Backup DB?')
        msg.setTextFormat(Qt.RichText)
        msg.setText("<b><span style='color:red'>WARNING! This is a potentially destructive operation!<br>It is recommmended to back up the database before proceeding.</span></b><br><br>Do you want to back up the current DB before making changes?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        reply = msg.exec()
        pre_path = None
        if reply == QMessageBox.Yes:
            pre_path = db + f'.bak_{int(time.time())}'
            try:
                shutil.copy2(db, pre_path)
            except Exception as e:
                QMessageBox.warning(self, 'Warning', f'Could not create backup: {e}')

        # simulate counts and show a pre-transfer summary dialog for user confirmation
        sim = db_utils.simulate_update_counts(db, source_id, cats, source_is_guild=False)
        sel_items = getattr(self, 'selected_item_ids', None) or []
        sel_buildings = getattr(self, 'selected_building_object_ids', None) or []
        sel_thralls = getattr(self, 'selected_thrall_ids', None) or []
        if not self.show_pretransfer_summary(sim, len(sel_items), len(sel_buildings), len(sel_thralls)):
            return

        # collect selected per-object ids if any
        item_ids = getattr(self, 'selected_item_ids', None)
        building_ids = getattr(self, 'selected_building_object_ids', None)
        thrall_ids = getattr(self, 'selected_thrall_ids', None)
        set_guild = False
        target_is_guild = False
        include_discovered = self.cb_include_discovered.isChecked()
        source_is_guild = False
        # Record before/after counts for audit
        before_source = db_utils.counts_for_owner(db, source_id)
        before_target = db_utils.counts_for_owner(db, target_id)
        success, changed, msg = db_utils.perform_transfer(
            db, source_id, target_id, cats, dry_run=False,
            item_ids=item_ids, building_object_ids=building_ids, thrall_ids=thrall_ids,
            set_source_guild_to_target=set_guild, target_is_guild=target_is_guild,
            include_discovered_owner_columns=include_discovered, source_is_guild=source_is_guild
        )
        after_source = db_utils.counts_for_owner(db, source_id)
        after_target = db_utils.counts_for_owner(db, target_id)
        if not success:
            QMessageBox.critical(self, 'Transfer Failed', msg)
            return

        self.table.setRowCount(0)
        rows = [
            ('Items (inventory)', changed.get('item_inventory', 0)),
            ('Item properties', changed.get('item_properties', 0)),
            ('Buildings', changed.get('buildings', 0)),
            ('Thralls/Pets', changed.get('thralls', 0)),
            ('GameEvents owner', changed.get('game_events_owner', 0)),
        ]
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(r[0]))
            self.table.setItem(i, 1, QTableWidgetItem(str(r[1])))
            self.table.setItem(i, 2, QTableWidgetItem(str(r[1])))

        # Inform user; if some thralls were skipped due to existing ownership, include that info
        skipped = changed.get('skipped_thralls') if isinstance(changed, dict) else None
        if skipped:
            # show count and first few IDs
            displayed = ','.join(str(x) for x in (skipped[:10]))
            more = f' (and {len(skipped)-10} more)' if len(skipped) > 10 else ''
            QMessageBox.information(self, 'Transfer Complete', f'Transfer finished. Changes made in: {db}\nSkipped {len(skipped)} thrall(s) because target already owned them: {displayed}{more}')
        else:
            QMessageBox.information(self, 'Transfer Complete', f'Transfer finished. Changes made in: {db}')

        # write audit CSV entry with before/after counts
        audit_csv = APP_DIR / 'transfers_audit.csv'
        record = {
            'timestamp': int(time.time()),
            'db_path': str(db),
            'pre_transfer_backup': pre_path or '',
            'source_id': source_id,
            'target_id': target_id,
            'categories': cats,
            'item_ids': item_ids or [],
            'building_object_ids': building_ids or [],
            'thrall_ids': thrall_ids or [],
            'changed_json': changed,
            'message': msg,
            'before_source': before_source,
            'after_source': after_source,
            'before_target': before_target,
            'after_target': after_target
        }
        try:
            db_utils.write_audit_csv(str(audit_csv), record)
        except Exception as e:
            import traceback
            db_utils._log(f'Audit log write failed: {e}\n{traceback.format_exc()}')
            QMessageBox.warning(self, 'Audit Warning', f'Failed to write audit CSV: {e}\nSee transfer.log for details.')


if __name__ == '__main__':
    import time
    app = QApplication(sys.argv)
    # Set application and main window icon (use icon.ico if present)
    try:
        ico = QIcon(str(APP_DIR / 'icon.ico'))
        if not ico.isNull():
            app.setWindowIcon(ico)
    except Exception:
        pass
    w = TransferApp()
    try:
        # also set window icon on the main window
        w.setWindowIcon(QIcon(str(APP_DIR / 'icon.ico')))
    except Exception:
        pass
    w.show()
    sys.exit(app.exec())
