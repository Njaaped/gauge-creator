# app_ui.py
# This file defines the main application window (QMainWindow),
# handles all GUI elements, layouts, signal/slot connections,
# and manages the worker thread for video generation.

import sys
import os
from datetime import datetime

# Import the new custom graph widget
from graph_widget import GraphWidget

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QFileDialog, QLabel,
                             QGridLayout, QGroupBox, QComboBox, QMessageBox,
                             QDateTimeEdit, QApplication)
from PyQt6.QtCore import QDateTime, Qt, QThread, QObject, pyqtSignal
from PyQt6.QtGui import QFont

# Import backend functions
import backend_logic
import gauge_generator

# --- Worker for Threaded Video Generation (Now Simplified) ---
class GenerationWorker(QObject):
    """
    A worker object that runs in a separate thread. It now simply calls the
    centralized backend orchestrator function to do the heavy lifting.
    """
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, tcx_data, start_time, end_time, output_path):
        super().__init__()
        self.tcx_data = tcx_data
        self.start_time = start_time
        self.end_time = end_time
        self.output_path = output_path

    def run(self):
        """The main work method now delegates to the backend orchestrator."""
        try:
            # Single call to the new, centralized logic.
            # We pass self.progress.emit directly as the callback function.
            final_path = backend_logic.orchestrate_video_generation(
                self.tcx_data, self.start_time, self.end_time, self.output_path, self.progress.emit
            )
            self.finished.emit(final_path)
        except Exception as e:
            self.error.emit(f"An error occurred during generation: {e}")


# --- Main Application Window (UI setup is unchanged) ---
class MainWindow(QMainWindow):
    """Main application window class."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cycling Data Video Generator")
        self.setGeometry(100, 100, 900, 700)

        # --- Instance variables ---
        self.tcx_path = None
        self.tcx_metadata = {}
        self.generation_thread = None
        self.generation_worker = None

        # --- Main Layout ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)

        # --- Initialize UI components ---
        self._create_file_input_group()
        self._create_graph_and_time_group()
        self._create_generation_group()

        self.update_ui_state()

    def _create_file_input_group(self):
        """Creates the file loading section of the UI."""
        group = QGroupBox("1. Load Data File")
        layout = QGridLayout()

        self.load_tcx_btn = QPushButton("Load TCX File")
        self.load_tcx_btn.clicked.connect(self.load_tcx)
        self.tcx_path_display = QLineEdit("No TCX file loaded")
        self.tcx_path_display.setReadOnly(True)

        layout.addWidget(self.load_tcx_btn, 0, 0)
        layout.addWidget(self.tcx_path_display, 0, 1)

        group.setLayout(layout)
        self.main_layout.addWidget(group)

    def _create_graph_and_time_group(self):
        """Creates the graph for data visualization and time selection."""
        group = QGroupBox("2. Select Time Range")
        layout = QVBoxLayout()

        # --- Instantiate the custom GraphWidget ---
        self.graph_widget = GraphWidget()
        self.graph_widget.setMinimumHeight(300)
        # Connect the custom signal to our handler
        self.graph_widget.regionChanged.connect(self.on_region_changed)
        layout.addWidget(self.graph_widget)

        # --- Time Edit Fields ---
        time_edits_layout = QGridLayout()
        time_edits_layout.addWidget(QLabel("Segment Start Time:"), 0, 0)
        self.start_time_edit = QDateTimeEdit()
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time_edit.dateTimeChanged.connect(self.update_ui_state)
        time_edits_layout.addWidget(self.start_time_edit, 0, 1)
        
        time_edits_layout.addWidget(QLabel("Segment End Time:"), 1, 0)
        self.end_time_edit = QDateTimeEdit()
        self.end_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_time_edit.dateTimeChanged.connect(self.update_ui_state)
        time_edits_layout.addWidget(self.end_time_edit, 1, 1)
        
        layout.addLayout(time_edits_layout)
        group.setLayout(layout)
        self.main_layout.addWidget(group)

    def _create_generation_group(self):
        """Creates the final video generation action section."""
        group = QGroupBox("3. Generation")
        layout = QVBoxLayout()

        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Dashboard Style:"))
        self.dashboard_style_combo = QComboBox()
        self.dashboard_style_combo.addItem("Power Dashboard")
        style_layout.addWidget(self.dashboard_style_combo)
        style_layout.addStretch()

        self.generate_btn = QPushButton("Generate Video")
        self.generate_btn.clicked.connect(self.start_generation)
        self.status_label = QLabel("Status: Load a TCX file to begin.")
        self.status_label.setStyleSheet("color: #555;")

        layout.addLayout(style_layout)
        layout.addWidget(self.generate_btn)
        layout.addWidget(self.status_label)
        group.setLayout(layout)
        self.main_layout.addWidget(group)
        self.main_layout.addStretch()

    # --- SLOTS / EVENT HANDLERS ---
    def load_tcx(self):
        """Opens a file dialog to select a TCX file, parses, and plots it."""
        path, _ = QFileDialog.getOpenFileName(self, "Load TCX", "", "TCX Files (*.tcx)")
        if path:
            self.tcx_path = path
            self.tcx_path_display.setText(path)
            self.status_label.setText("Status: Parsing TCX file...")
            QApplication.processEvents()
            
            try:
                self.tcx_metadata = backend_logic.parse_tcx_file(self.tcx_path)
                self.status_label.setText("Status: Plotting data...")
                QApplication.processEvents()
                self.graph_widget.plot_data(self.tcx_metadata['trackpoints'])
                self.status_label.setText("Status: TCX file loaded. Drag on the graph to select a range.")
            except ValueError as e:
                # Catch the specific ValueError from our backend for better messages
                self.show_error_message(str(e))
                self.tcx_metadata = {} # Clear bad data
            except Exception as e:
                # Catch any other unexpected errors
                self.show_error_message(f"An unexpected error occurred: {e}")
                self.tcx_metadata = {}

        self.update_ui_state()

    def on_region_changed(self, start_timestamp, end_timestamp):
        """Handler for when the user drags or resizes the selection region."""
        start_dt = QDateTime.fromSecsSinceEpoch(start_timestamp)
        end_dt = QDateTime.fromSecsSinceEpoch(end_timestamp)

        self.start_time_edit.blockSignals(True)
        self.end_time_edit.blockSignals(True)
        self.start_time_edit.setDateTime(start_dt)
        self.end_time_edit.setDateTime(end_dt)
        self.start_time_edit.blockSignals(False)
        self.end_time_edit.blockSignals(False)

        self.update_ui_state()

    def update_ui_state(self):
        """Validates inputs and enables/disables the Generate button."""
        is_valid = True
        status_message = "Status: Ready."

        if not self.tcx_path or not self.tcx_metadata.get('trackpoints'):
            is_valid = False
            status_message = "Status: Please load a valid TCX file."
        else:
            segment_start = self.start_time_edit.dateTime().toPyDateTime()
            segment_end = self.end_time_edit.dateTime().toPyDateTime()
            if not (segment_start < segment_end):
                is_valid = False
                status_message = "Status: Start time must be before end time."

        self.generate_btn.setEnabled(is_valid)
        if is_valid:
             self.status_label.setText("Status: Ready to generate video for the selected range.")
        else:
             self.status_label.setText(status_message)

    def start_generation(self):
        """Initiates the video generation process in a separate thread."""
        output_path, _ = QFileDialog.getSaveFileName(self, "Save Generated Video", "", "MP4 Video (*.mp4)")
        if not output_path:
            return
        if not output_path.lower().endswith('.mp4'):
            output_path += '.mp4'

        self.generate_btn.setEnabled(False)
        self.status_label.setText("Status: Starting generation...")

        start_time = self.start_time_edit.dateTime().toPyDateTime()
        end_time = self.end_time_edit.dateTime().toPyDateTime()
        tcx_data = self.tcx_metadata['trackpoints']
        
        self.generation_thread = QThread()
        self.generation_worker = GenerationWorker(tcx_data, start_time, end_time, output_path)
        self.generation_worker.moveToThread(self.generation_thread)

        self.generation_thread.started.connect(self.generation_worker.run)
        self.generation_worker.finished.connect(self.on_generation_finished)
        self.generation_worker.error.connect(self.on_generation_error)
        self.generation_worker.progress.connect(lambda p, m: self.status_label.setText(f"Status: {m} ({p}%)"))

        self.generation_worker.finished.connect(self.generation_thread.quit)
        self.generation_worker.finished.connect(self.generation_worker.deleteLater)
        self.generation_thread.finished.connect(self.generation_thread.deleteLater)
        self.generation_thread.start()

    def on_generation_finished(self, output_path):
        self.update_ui_state()
        QMessageBox.information(self, "Success", f"Video generation complete!\nSaved to: {output_path}")

    def on_generation_error(self, error_message):
        self.update_ui_state()
        self.show_error_message(error_message)

    def show_error_message(self, message):
        QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        if self.generation_thread and self.generation_thread.isRunning():
            self.generation_thread.quit()
            self.generation_thread.wait()
        event.accept()