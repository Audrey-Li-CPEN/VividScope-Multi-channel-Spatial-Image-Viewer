"""
VividScope - Multichannel Spatial Navigator
A professional MIBI image viewer with FIJI-style Adjustment Sliders
Built with napari
"""

import os
# Set Qt backend to PyQt5 (for development)
# NOTE: For commercial distribution, you have two options:
# 1. Purchase PyQt5 commercial license from Riverbank Computing
# 2. Switch to PySide6 (LGPL, free for commercial use) - requires Visual C++ Redistributables on Windows
#    Install: pip install PySide6
#    Then change QT_API to 'pyside6'
os.environ.setdefault('QT_API', 'pyqt5')

import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import tifffile
import napari
from napari.layers import Image
from napari.utils import Colormap
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QSlider, QSpinBox, QDoubleSpinBox, QGroupBox, QScrollArea,
    QFileDialog, QComboBox, QCheckBox, QSplitter, QProgressBar,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QSizePolicy,
    QColorDialog
)
from qtpy.QtGui import QColor, QIcon
from qtpy.QtCore import Qt, QTimer, QObject
from qtpy.QtWidgets import QApplication
import warnings
warnings.filterwarnings('ignore')


class ChannelAdjustmentWidget(QWidget):
    """Widget for adjusting a single channel (brightness, contrast, gamma)"""
    
    def __init__(self, channel_name: str, parent=None, visibility_callback=None, 
                 overlay_callback=None, color_callback=None):
        super().__init__(parent)
        self.channel_name = channel_name
        self.brightness = 0.0
        self.contrast = 1.0
        self.gamma = 1.0
        self.min_val = 0.0
        self.max_val = 1.0
        self.visibility_callback = visibility_callback
        self.overlay_callback = overlay_callback
        self.color_callback = color_callback
        self.is_collapsed = False
        self.channel_color = QColor(255, 255, 255)  # Default white/gray
        
        self.setup_ui()
        
    def setup_ui(self):
        # Modern styling for adjustment widgets
        self.setStyleSheet("""
            QGroupBox {
                font-weight: 500;
                font-size: 9pt;
                color: #D0D0D0;
                border: 1px solid rgba(100, 100, 110, 150);
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: rgba(35, 35, 40, 100);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 5px 0 5px;
                color: #C0C0C0;
            }
            QSlider::groove:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(50, 50, 55, 255),
                    stop:1 rgba(60, 60, 65, 255));
                height: 6px;
                border-radius: 3px;
                border: 1px solid rgba(80, 80, 90, 200);
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(220, 220, 230, 255),
                    stop:1 rgba(200, 200, 210, 255));
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
                border: 1px solid rgba(100, 100, 110, 255);
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(240, 240, 250, 255),
                    stop:1 rgba(220, 220, 230, 255));
            }
            QDoubleSpinBox, QSpinBox {
                background-color: rgba(40, 40, 45, 200);
                color: white;
                border: 1px solid rgba(100, 100, 110, 200);
                border-radius: 4px;
                padding: 4px;
            }
            QDoubleSpinBox:focus, QSpinBox:focus {
                border: 1px solid rgba(120, 150, 200, 255);
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(60, 60, 70, 255),
                    stop:1 rgba(50, 50, 60, 255));
                color: white;
                border: 1px solid rgba(100, 100, 110, 200);
                border-radius: 4px;
                padding: 6px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(70, 70, 80, 255),
                    stop:1 rgba(60, 60, 70, 255));
            }
            QCheckBox {
                color: #E0E0E0;
                font-weight: 500;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid rgba(100, 100, 110, 200);
                border-radius: 3px;
                background-color: rgba(40, 40, 45, 200);
            }
            QCheckBox::indicator:checked {
                background-color: rgba(80, 120, 180, 255);
                border: 1px solid rgba(100, 140, 200, 255);
            }
        """)
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Channel name and visibility - make it clickable to collapse/expand
        name_layout = QHBoxLayout()
        name_label = QLabel(f"<b style='color: #E0E0E0; font-size: 11pt;'>{self.channel_name}</b>")
        name_label.setAlignment(Qt.AlignLeft)
        name_label.setStyleSheet("padding: 5px; background-color: rgba(50, 50, 55, 150); border-radius: 4px;")
        # Make label clickable by installing event filter
        name_label.mousePressEvent = lambda e: self.toggle_collapse()
        name_label.setToolTip("Click to collapse/expand controls")
        name_layout.addWidget(name_label)
        
        self.visible_checkbox = QCheckBox("Visible")
        self.visible_checkbox.setChecked(True)
        if self.visibility_callback:
            self.visible_checkbox.stateChanged.connect(self.visibility_callback)
        name_layout.addWidget(self.visible_checkbox)
        
        # Overlay checkbox for multichannel mode
        self.overlay_checkbox = QCheckBox("Overlay")
        self.overlay_checkbox.setChecked(True)
        self.overlay_checkbox.setToolTip("Include this channel in multichannel overlay")
        if self.overlay_callback:
            self.overlay_checkbox.stateChanged.connect(self.overlay_callback)
        name_layout.addWidget(self.overlay_checkbox)
        
        layout.addLayout(name_layout)
        
        # Container for all adjustment controls (can be hidden)
        self.controls_container = QWidget()
        self.controls_layout = QVBoxLayout()
        self.controls_layout.setSpacing(3)  # More compact
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Color picker for multichannel mode
        color_group = QGroupBox("Color (Multichannel)")
        color_layout = QHBoxLayout()
        
        self.color_button = QPushButton()
        self.color_button.setMinimumHeight(30)
        self.color_button.setMaximumWidth(100)
        self.color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb({self.channel_color.red()}, {self.channel_color.green()}, {self.channel_color.blue()});
                border: 2px solid rgba(100, 100, 110, 200);
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid rgba(150, 150, 160, 255);
            }}
        """)
        self.color_button.clicked.connect(self.pick_color)
        self.color_button.setToolTip("Click to change channel color for multichannel overlay")
        
        color_layout.addWidget(QLabel("Color:"))
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        color_group.setLayout(color_layout)
        self.controls_layout.addWidget(color_group)
        
        # Brightness control
        brightness_group = QGroupBox("Brightness")
        brightness_layout = QVBoxLayout()
        
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_spinbox = QDoubleSpinBox()
        self.brightness_spinbox.setRange(-1.0, 1.0)
        self.brightness_spinbox.setSingleStep(0.01)
        self.brightness_spinbox.setDecimals(2)
        self.brightness_spinbox.setValue(0.0)
        
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_spinbox)
        brightness_group.setLayout(brightness_layout)
        self.controls_layout.addWidget(brightness_group)
        
        # Contrast control
        contrast_group = QGroupBox("Contrast")
        contrast_layout = QVBoxLayout()
        
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(1, 200)
        self.contrast_slider.setValue(100)
        self.contrast_spinbox = QDoubleSpinBox()
        self.contrast_spinbox.setRange(0.01, 2.0)
        self.contrast_spinbox.setSingleStep(0.01)
        self.contrast_spinbox.setDecimals(2)
        self.contrast_spinbox.setValue(1.0)
        
        contrast_layout.addWidget(self.contrast_slider)
        contrast_layout.addWidget(self.contrast_spinbox)
        contrast_group.setLayout(contrast_layout)
        self.controls_layout.addWidget(contrast_group)
        
        # Gamma control
        gamma_group = QGroupBox("Gamma")
        gamma_layout = QVBoxLayout()
        
        self.gamma_slider = QSlider(Qt.Horizontal)
        self.gamma_slider.setRange(1, 500)
        self.gamma_slider.setValue(100)
        self.gamma_spinbox = QDoubleSpinBox()
        self.gamma_spinbox.setRange(0.01, 5.0)
        self.gamma_spinbox.setSingleStep(0.01)
        self.gamma_spinbox.setDecimals(2)
        self.gamma_spinbox.setValue(1.0)
        
        gamma_layout.addWidget(self.gamma_slider)
        gamma_layout.addWidget(self.gamma_spinbox)
        gamma_group.setLayout(gamma_layout)
        self.controls_layout.addWidget(gamma_group)
        
        # Min/Max display range
        range_group = QGroupBox("Display Range")
        range_layout = QHBoxLayout()
        
        self.min_spinbox = QDoubleSpinBox()
        self.min_spinbox.setRange(0.0, 1.0)
        self.min_spinbox.setSingleStep(0.01)
        self.min_spinbox.setDecimals(3)
        self.min_spinbox.setValue(0.0)
        
        self.max_spinbox = QDoubleSpinBox()
        self.max_spinbox.setRange(0.0, 1.0)
        self.max_spinbox.setSingleStep(0.01)
        self.max_spinbox.setDecimals(3)
        self.max_spinbox.setValue(1.0)
        
        range_layout.addWidget(QLabel("Min:"))
        range_layout.addWidget(self.min_spinbox)
        range_layout.addWidget(QLabel("Max:"))
        range_layout.addWidget(self.max_spinbox)
        range_group.setLayout(range_layout)
        self.controls_layout.addWidget(range_group)
        
        # Reset button
        reset_btn = QPushButton("Reset")
        reset_btn.setToolTip("Reset brightness, contrast, gamma, and display range for this channel to default values")
        reset_btn.clicked.connect(self.reset)
        self.controls_layout.addWidget(reset_btn)
        
        self.controls_container.setLayout(self.controls_layout)
        layout.addWidget(self.controls_container)
        
        # Connect signals
        self.brightness_slider.valueChanged.connect(
            lambda v: self.brightness_spinbox.setValue(v / 100.0)
        )
        self.brightness_spinbox.valueChanged.connect(
            lambda v: self.brightness_slider.setValue(int(v * 100))
        )
        
        self.contrast_slider.valueChanged.connect(
            lambda v: self.contrast_spinbox.setValue(v / 100.0)
        )
        self.contrast_spinbox.valueChanged.connect(
            lambda v: self.contrast_slider.setValue(int(v * 100))
        )
        
        self.gamma_slider.valueChanged.connect(
            lambda v: self.gamma_spinbox.setValue(v / 100.0)
        )
        self.gamma_spinbox.valueChanged.connect(
            lambda v: self.gamma_slider.setValue(int(v * 100))
        )
        
        self.setLayout(layout)
        
    def reset(self):
        """Reset all adjustments to default values"""
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(100)
        self.gamma_slider.setValue(100)
        self.min_spinbox.setValue(0.0)
        self.max_spinbox.setValue(1.0)
        
    def toggle_collapse(self):
        """Toggle collapse/expand of adjustment controls"""
        self.is_collapsed = not self.is_collapsed
        self.controls_container.setVisible(not self.is_collapsed)
    
    def pick_color(self):
        """Open color picker dialog"""
        color = QColorDialog.getColor(self.channel_color, self, "Select Channel Color")
        if color.isValid():
            self.channel_color = color
            # Update button color
            self.color_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgb({color.red()}, {color.green()}, {color.blue()});
                    border: 2px solid rgba(100, 100, 110, 200);
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 2px solid rgba(150, 150, 160, 255);
                }}
            """)
            # Notify parent of color change
            if self.color_callback:
                self.color_callback(color)
    
    def get_color(self) -> QColor:
        """Get current channel color"""
        return self.channel_color
    
    def set_color(self, color: QColor):
        """Set channel color"""
        self.channel_color = color
        self.color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb({color.red()}, {color.green()}, {color.blue()});
                border: 2px solid rgba(100, 100, 110, 200);
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid rgba(150, 150, 160, 255);
            }}
        """)
    
    def get_adjustments(self) -> Dict:
        """Get current adjustment values"""
        return {
            'brightness': self.brightness_spinbox.value(),
            'contrast': self.contrast_spinbox.value(),
            'gamma': self.gamma_spinbox.value(),
            'min': self.min_spinbox.value(),
            'max': self.max_spinbox.value()
        }


class VividScopeViewer(QObject):
    """VividScope - Multichannel Spatial Navigator Application"""
    
    def __init__(self):
        QObject.__init__(self)  # Initialize QObject parent
        self.viewer = napari.Viewer(title="VividScope - Multichannel Spatial Navigator")
        # Store raw image data (original format)
        self.channel_raw_data: Dict[str, np.ndarray] = {}
        # Store normalization factors (max value for each channel)
        self.channel_max_values: Dict[str, float] = {}
        # Store file paths for lazy loading
        self.channel_files: Dict[str, Path] = {}
        # Cache normalized images (0-1 range)
        self.channel_normalized_cache: Dict[str, np.ndarray] = {}
        # Cache adjusted images
        self.channel_adjusted_cache: Dict[str, np.ndarray] = {}
        self.channel_layers: Dict[str, Image] = {}
        self.adjustment_widgets: Dict[str, ChannelAdjustmentWidget] = {}
        self.current_folder: Optional[Path] = None
        self.single_channel_active: bool = False
        self.channel_list: List[str] = []  # Ordered list of channels for slider
        self.previous_visibility_state: Dict[str, bool] = {}  # Store visibility before single channel mode
        self.channel_colors: Dict[str, QColor] = {}  # Store colors for each channel
        self.channel_colormaps: Dict[str, Colormap] = {}  # Store custom colormaps for each channel
        self._updating_slider_position = False  # Flag to prevent recursive updates
        self._slider_update_timer = None  # Timer for debounced updates
        self._is_loading = False  # Flag to prevent slider updates during loading
        self._update_timers: Dict[str, QTimer] = {}  # Timers for debounced channel updates
        
        self.setup_ui()
        
        # Set window icon if available
        self._set_window_icon()
        
        # Initialize view mode button text and slider state
        if hasattr(self, 'single_channel_mode_btn'):
            self.update_view_mode_button_text()
        if hasattr(self, 'channel_slider'):
            self.update_slider_state()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Create dock widget for controls with modern styling
        controls_widget = QWidget()
        controls_widget.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
            }
            QGroupBox {
                font-weight: 600;
                font-size: 11pt;
                color: #E0E0E0;
                border: 2px solid rgba(100, 100, 110, 200);
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: rgba(40, 40, 45, 150);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #D0D0D0;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(60, 60, 70, 255),
                    stop:1 rgba(50, 50, 60, 255));
                color: white;
                border: 1px solid rgba(100, 100, 110, 200);
                border-radius: 6px;
                padding: 8px;
                font-weight: 500;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(70, 70, 80, 255),
                    stop:1 rgba(60, 60, 70, 255));
                border: 1px solid rgba(120, 150, 200, 255);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(50, 50, 60, 255),
                    stop:1 rgba(40, 40, 50, 255));
            }
            QLineEdit {
                background-color: rgba(40, 40, 45, 200);
                color: white;
                border: 1px solid rgba(100, 100, 110, 200);
                border-radius: 4px;
                padding: 6px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 2px solid rgba(120, 150, 200, 255);
                background-color: rgba(45, 45, 50, 200);
            }
            QListWidget {
                background-color: rgba(35, 35, 40, 200);
                color: white;
                border: 1px solid rgba(100, 100, 110, 200);
                border-radius: 4px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 4px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: rgba(80, 120, 180, 255);
                color: white;
            }
            QListWidget::item:hover {
                background-color: rgba(60, 90, 140, 255);
            }
            QLabel {
                color: #E0E0E0;
            }
        """)
        # Create ONE big scroll area for the entire right panel (from Load button to Global Controls)
        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(False)  # Keep natural widget size for proper scrolling
        self.main_scroll.setMinimumWidth(300)
        # Use Expanding policy to fill available space and allow horizontal expansion
        self.main_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Always show large vertical scrollbar on the right side
        self.main_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Style the scrollbar to be more prominent (like website scrollbars)
        scrollbar = self.main_scroll.verticalScrollBar()
        scrollbar.setStyleSheet("""
            QScrollBar:vertical {
                background: rgba(40, 40, 45, 200);
                width: 20px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: rgba(120, 120, 130, 255);
                min-height: 30px;
                border-radius: 10px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(140, 140, 150, 255);
            }
            QScrollBar::handle:vertical:pressed {
                background: rgba(100, 100, 110, 255);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        
        # Create container for ALL content (Load button through Global Controls)
        self.main_scroll_container = QWidget()
        self.main_scroll_layout = QVBoxLayout()
        self.main_scroll_layout.setSpacing(12)
        self.main_scroll_layout.setContentsMargins(12, 12, 12, 12)
        self.main_scroll_layout.setAlignment(Qt.AlignTop)
        self.main_scroll_container.setLayout(self.main_scroll_layout)
        
        # Container should expand to fit all content and adapt to width changes
        self.main_scroll_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        
        # Load folder button with enhanced styling
        self.load_btn = QPushButton("Load MIBI Folder")
        self.load_btn.setMinimumHeight(45)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(80, 120, 180, 255),
                    stop:1 rgba(60, 100, 160, 255));
                color: white;
                border: 1px solid rgba(100, 140, 200, 255);
                border-radius: 6px;
                padding: 10px;
                font-weight: 600;
                font-size: 11pt;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(90, 130, 190, 255),
                    stop:1 rgba(70, 110, 170, 255));
                border: 1px solid rgba(120, 160, 220, 255);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(70, 110, 170, 255),
                    stop:1 rgba(50, 90, 150, 255));
            }
        """)
        self.load_btn.clicked.connect(self.load_folder)
        self.main_scroll_layout.addWidget(self.load_btn)
        
        # View Mode Toggle (prominent button with both options shown)
        view_mode_group = QGroupBox("View Mode")
        view_mode_layout = QVBoxLayout()
        view_mode_layout.setSpacing(8)
        
        # Create custom button widget with two labels for dimming support
        self.single_channel_mode_btn = QPushButton()
        self.single_channel_mode_btn.setMinimumHeight(60)  # Increased height for 2-line display
        self.single_channel_mode_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(70, 110, 150, 255),
                    stop:1 rgba(60, 100, 140, 255));
                border: 2px solid rgba(100, 140, 180, 255);
                border-radius: 6px;
                padding: 0px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(80, 120, 160, 255),
                    stop:1 rgba(70, 110, 150, 255));
                border: 2px solid rgba(120, 160, 200, 255);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(60, 100, 140, 255),
                    stop:1 rgba(50, 90, 130, 255));
            }
        """)
        
        # Create layout inside button for labels
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(10, 8, 10, 8)  # Increased vertical padding
        btn_layout.setSpacing(10)
        
        self.single_channel_label = QLabel("Single\nChannel")
        self.single_channel_label.setAlignment(Qt.AlignCenter)
        self.single_channel_label.setWordWrap(True)  # Enable word wrapping
        self.single_channel_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: 700;
                font-size: 10pt;
                background: transparent;
                border: none;
            }
        """)
        
        separator_label = QLabel("|")
        separator_label.setAlignment(Qt.AlignCenter)
        separator_label.setStyleSheet("""
            QLabel {
                color: rgba(200, 200, 200, 200);
                font-weight: 500;
                font-size: 11pt;
                background: transparent;
                border: none;
            }
        """)
        
        self.multi_channel_label = QLabel("Multi-\nChannel")
        self.multi_channel_label.setAlignment(Qt.AlignCenter)
        self.multi_channel_label.setWordWrap(True)  # Enable word wrapping
        self.multi_channel_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: 700;
                font-size: 10pt;
                background: transparent;
                border: none;
            }
        """)
        
        btn_layout.addWidget(self.single_channel_label)
        btn_layout.addWidget(separator_label)
        btn_layout.addWidget(self.multi_channel_label)
        
        # Set layout on button
        self.single_channel_mode_btn.setLayout(btn_layout)
        self.single_channel_mode_btn.setToolTip("Click to toggle between Single Channel and Multi-Channel viewing modes")
        self.single_channel_mode_btn.clicked.connect(self.toggle_single_channel_mode_btn)
        view_mode_layout.addWidget(self.single_channel_mode_btn)
        
        view_mode_group.setLayout(view_mode_layout)
        self.main_scroll_layout.addWidget(view_mode_group)
        
        # Channel selection
        channel_group = QGroupBox("Channels")
        channel_layout = QVBoxLayout()
        
        # Keep combo box for backward compatibility but hide it
        self.channel_combo = QComboBox()
        self.channel_combo.currentTextChanged.connect(self.on_channel_selected)
        self.channel_combo.setVisible(False)
        
        # Add helpful info
        info_label = QLabel("Tip: Use 'Find Channel' search or 'Quick Select' list to navigate")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-size: 9pt; padding: 5px; font-style: italic;")
        channel_layout.addWidget(info_label)
        
        show_all_btn = QPushButton("Show All Channels")
        show_all_btn.setMinimumHeight(35)
        show_all_btn.setToolTip("Show all loaded channels. In multichannel mode, respects overlay checkboxes.")
        show_all_btn.clicked.connect(self.show_all_channels)
        channel_layout.addWidget(show_all_btn)
        
        hide_all_btn = QPushButton("Hide All Channels")
        hide_all_btn.setMinimumHeight(35)
        hide_all_btn.setToolTip("Hide all channels from the display")
        hide_all_btn.clicked.connect(self.hide_all_channels)
        channel_layout.addWidget(hide_all_btn)
        
        channel_group.setLayout(channel_layout)
        self.main_scroll_layout.addWidget(channel_group)
        
        # Progress bar for loading
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.main_scroll_layout.addWidget(self.progress_label)
        self.main_scroll_layout.addWidget(self.progress_bar)
        
        # Channel search/filter
        search_group = QGroupBox("Find Channel")
        search_layout = QVBoxLayout()
        
        self.channel_search = QLineEdit()
        self.channel_search.setPlaceholderText("Type to search channels...")
        self.channel_search.setToolTip("Type channel name to filter and navigate to adjustment controls")
        self.channel_search.textChanged.connect(self.filter_channels)
        search_layout.addWidget(self.channel_search)
        
        # Compact channel list for quick navigation
        self.channel_list_widget = QListWidget()
        self.channel_list_widget.setMaximumHeight(120)
        self.channel_list_widget.setToolTip("Quick select a channel to jump to its adjustment controls")
        self.channel_list_widget.itemClicked.connect(self.on_channel_list_selected)
        search_layout.addWidget(QLabel("Quick Select:"))
        search_layout.addWidget(self.channel_list_widget)
        
        search_group.setLayout(search_layout)
        self.main_scroll_layout.addWidget(search_group)
        
        # Adjustment widgets container (no separate scroll area - part of main scroll)
        self.adjustments_container = QWidget()
        self.adjustments_layout = QVBoxLayout()
        self.adjustments_layout.setSpacing(5)
        self.adjustments_layout.setContentsMargins(5, 5, 5, 5)
        self.adjustments_layout.setAlignment(Qt.AlignTop)
        self.adjustments_container.setLayout(self.adjustments_layout)
        self.adjustments_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        
        # Add adjustments container to main scroll layout
        self.main_scroll_layout.addWidget(self.adjustments_container)
        
        # Global controls - add to main scroll layout
        global_group = QGroupBox("Global Controls")
        global_layout = QVBoxLayout()
        
        reset_all_btn = QPushButton("Reset All Channels")
        reset_all_btn.setMinimumHeight(35)
        reset_all_btn.setToolTip("Reset brightness, contrast, gamma, and display range for all channels to default values")
        reset_all_btn.clicked.connect(self.reset_all_channels)
        global_layout.addWidget(reset_all_btn)
        
        # Help/info button
        help_btn = QPushButton("Panel Information")
        help_btn.setMinimumHeight(35)
        help_btn.setToolTip("Click to see differences between left and right panels")
        help_btn.clicked.connect(self.show_panel_info)
        global_layout.addWidget(help_btn)
        
        global_group.setLayout(global_layout)
        self.main_scroll_layout.addWidget(global_group)
        
        # Set the main container as the scroll area's widget
        self.main_scroll.setWidget(self.main_scroll_container)
        
        # Create minimal outer layout - just add the scroll area
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(0)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.addWidget(self.main_scroll)
        
        # Store reference to main_scroll for compatibility with existing code
        self.adjustments_scroll = self.main_scroll
        
        controls_widget.setLayout(controls_layout)
        
        # Add dock widget to viewer
        self.viewer.window.add_dock_widget(
            controls_widget, 
            name="Adjustments",
            area="right"
        )
        
        # Create channel slider widget - always visible, but only enabled in single channel mode
        self.slider_container = QWidget()
        # Modern, sleek styling with gradient effect - supports enabled/disabled states
        self.slider_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 30, 35, 250),
                    stop:1 rgba(25, 25, 30, 250));
                border-top: 2px solid rgba(80, 80, 90, 255);
                border-left: none;
                border-right: none;
                border-bottom: none;
                border-radius: 0px;
                padding: 12px 20px;
            }
            QLabel {
                color: #E0E0E0;
                font-weight: 600;
                font-size: 13px;
            }
            QSlider::groove:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(50, 50, 55, 255),
                    stop:1 rgba(60, 60, 65, 255));
                height: 8px;
                border-radius: 4px;
                border: 1px solid rgba(100, 100, 110, 200);
            }
            QSlider::groove:horizontal:disabled {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(35, 35, 40, 255),
                    stop:1 rgba(40, 40, 45, 255));
                border: 1px solid rgba(60, 60, 70, 150);
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 255),
                    stop:0.5 rgba(240, 240, 245, 255),
                    stop:1 rgba(220, 220, 225, 255));
                width: 20px;
                height: 20px;
                margin: -7px 0;
                border-radius: 10px;
                border: 2px solid rgba(100, 100, 110, 255);
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 255),
                    stop:0.5 rgba(250, 250, 255, 255),
                    stop:1 rgba(240, 240, 245, 255));
                border: 2px solid rgba(120, 150, 200, 255);
            }
            QSlider::handle:horizontal:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(200, 200, 210, 255),
                    stop:0.5 rgba(180, 180, 190, 255),
                    stop:1 rgba(160, 160, 170, 255));
            }
            QSlider::handle:horizontal:disabled {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(100, 100, 105, 255),
                    stop:0.5 rgba(90, 90, 95, 255),
                    stop:1 rgba(80, 80, 85, 255));
                border: 2px solid rgba(60, 60, 70, 150);
            }
        """)
        slider_layout = QHBoxLayout()
        slider_layout.setContentsMargins(25, 15, 25, 15)
        slider_layout.setSpacing(20)
        
        # Channel label with improved styling - shows mode status
        self.channel_label = QLabel("Channel:")
        self.channel_label.setStyleSheet("""
            QLabel {
                color: #D0D0D0;
                font-weight: 600;
                font-size: 13px;
                padding: 2px 0px;
            }
        """)
        slider_layout.addWidget(self.channel_label)
        
        self.channel_slider = QSlider(Qt.Horizontal)
        self.channel_slider.setMinimum(0)
        self.channel_slider.setMaximum(0)
        self.channel_slider.setValue(0)
        self.channel_slider.setEnabled(False)
        self.channel_slider.valueChanged.connect(self.on_slider_changed)
        # Slider will expand to fill available space (match canvas width)
        self.channel_slider.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )
        slider_layout.addWidget(self.channel_slider)
        
        # Improved label styling - supports enabled/disabled states
        self.channel_slider_label = QLabel("0/0")
        self.channel_slider_label.setMinimumWidth(100)
        self.channel_slider_label.setAlignment(Qt.AlignCenter)
        self.channel_slider_label.setStyleSheet("""
            QLabel {
                background: rgba(40, 40, 45, 200);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13px;
                padding: 6px 12px;
                border-radius: 6px;
                border: 1px solid rgba(100, 100, 110, 200);
            }
        """)
        slider_layout.addWidget(self.channel_slider_label)
        
        self.slider_container.setLayout(slider_layout)
        self.slider_container.setVisible(True)  # Always visible
        self.slider_container.setFixedHeight(70)  # Slightly taller for better appearance
        # Initially disabled (will be enabled in single channel mode)
        self.channel_slider.setEnabled(False)
        # Make container expand horizontally to match canvas width
        self.slider_container.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )
        
        # Add slider as an overlay widget directly on the canvas (positioned at bottom of canvas)
        # Use a small delay to ensure the viewer window is fully initialized
        QTimer.singleShot(200, lambda: self._setup_slider_overlay())
    
    def _setup_slider_overlay(self):
        """Setup the slider as an overlay on the canvas - positioned at bottom of canvas"""
        try:
            # Get the qt_viewer which contains the canvas
            qt_viewer = self.viewer.window.qt_viewer
            if not qt_viewer:
                # Retry after a delay if viewer not ready (max 3 retries)
                if not hasattr(self, '_slider_setup_retries'):
                    self._slider_setup_retries = 0
                if self._slider_setup_retries < 3:
                    self._slider_setup_retries += 1
                    QTimer.singleShot(300, lambda: self._setup_slider_overlay())
                return
            
            # Reset retry counter on success
            self._slider_setup_retries = 0
            
            # Find the parent QWidget that contains the canvas
            parent_widget = None
            try:
                if isinstance(qt_viewer, QWidget):
                    parent_widget = qt_viewer
                else:
                    main_window = self.viewer.window._qt_window
                    if main_window:
                        central_widget = main_window.centralWidget()
                        if central_widget:
                            parent_widget = central_widget
                        else:
                            parent_widget = main_window
            except:
                try:
                    parent_widget = self.viewer.window._qt_window
                except:
                    pass
            
            if not isinstance(parent_widget, QWidget):
                return  # Can't setup without valid parent
            
            # Set the slider container as a child of the parent widget
            self.slider_container.setParent(parent_widget)
            
            # Configure widget attributes
            self.slider_container.setWindowFlags(Qt.Widget)
            self.slider_container.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self.slider_container.setAttribute(Qt.WA_ShowWithoutActivating, True)
            self.slider_container.setAttribute(Qt.WA_LayoutOnEntireRect, False)
            self.slider_container.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            self.slider_container.setFixedHeight(70)
            
            # Set initial visibility
            if not self._is_loading:
                self.slider_container.setVisible(True)
                self._debounced_update_slider_position()
            
            # Connect to resize events
            try:
                parent_widget.installEventFilter(self)
                main_window = self.viewer.window._qt_window
                if main_window and main_window != parent_widget:
                    main_window.installEventFilter(self)
            except:
                pass
            
            # Update label to show disabled state
            self.update_slider_state()
        except Exception as e:
            # Log error but don't retry indefinitely
            print(f"Error setting up slider overlay: {e}")
    
    def _debounced_update_slider_position(self):
        """Debounced update to prevent multiple rapid updates causing layout thrashing"""
        # Cancel any pending update
        if self._slider_update_timer:
            self._slider_update_timer.stop()
        
        # Schedule a single update after a short delay
        self._slider_update_timer = QTimer()
        self._slider_update_timer.setSingleShot(True)
        self._slider_update_timer.timeout.connect(self._update_slider_overlay_position)
        self._slider_update_timer.start(150)  # 150ms debounce
    
    def _update_slider_overlay_position(self):
        """Update the slider overlay position to be at the bottom of the canvas"""
        # Prevent recursive updates
        if self._updating_slider_position or self._is_loading:
            return
        
        if not hasattr(self, 'slider_container') or not self.slider_container:
            return
        
        try:
            self._updating_slider_position = True
            
            # Get the qt_viewer
            qt_viewer = self.viewer.window.qt_viewer
            if not qt_viewer:
                return
            
            # Get the parent widget
            parent_widget = self.slider_container.parent()
            if not parent_widget:
                self._setup_slider_overlay()
                return
            
            # Get dimensions from parent widget (simpler approach)
            try:
                if isinstance(qt_viewer, QWidget):
                    canvas_rect = qt_viewer.geometry()
                    canvas_x = canvas_rect.x()
                    canvas_y = canvas_rect.y()
                    canvas_width = canvas_rect.width()
                    canvas_height = canvas_rect.height()
                else:
                    # Fallback to parent widget dimensions
                    canvas_x = 0
                    canvas_y = 0
                    canvas_width = parent_widget.width()
                    canvas_height = parent_widget.height()
            except:
                # Last resort: use parent widget
                canvas_x = 0
                canvas_y = 0
                canvas_width = parent_widget.width()
                canvas_height = parent_widget.height()
            
            # Ensure minimum size
            if canvas_width < 100 or canvas_height < 100:
                return  # Not ready yet
            
            # Position slider at bottom of canvas
            slider_height = 70
            slider_y = canvas_y + max(0, canvas_height - slider_height)
            slider_width = canvas_width
            slider_x = canvas_x
            
            # Only update if position changed
            current_rect = self.slider_container.geometry()
            if (current_rect.x() != slider_x or current_rect.y() != slider_y or 
                current_rect.width() != slider_width or current_rect.height() != slider_height):
                
                self.slider_container.setGeometry(slider_x, slider_y, slider_width, slider_height)
                self.slider_container.raise_()
                self.slider_container.setVisible(True)
            
        except Exception as e:
            # Silently handle errors
            pass
        finally:
            self._updating_slider_position = False
        
        # Connect to layer events
        self.viewer.layers.events.inserted.connect(self.on_layer_added)
        self.viewer.layers.events.removed.connect(self.on_layer_removed)
        self.viewer.layers.selection.events.active.connect(self.on_layer_selected)
        
        # Track if we're updating selection internally (to avoid loops)
        self._updating_selection = False
        
        # Initialize view mode button text
        self.update_view_mode_button_text()
        
    def load_folder(self):
        """Load MIBI images from a folder (async with UI feedback)"""
        folder = QFileDialog.getExistingDirectory(
            None, 
            "Select MIBI Image Folder",
            str(Path.cwd())
        )
        
        if not folder:
            return
            
        folder_path = Path(folder)
        self.current_folder = folder_path
        
        # Disable button during loading
        self.load_btn.setEnabled(False)
        self.load_btn.setText("Loading...")
        
        # Set loading flag to prevent slider updates during loading
        self._is_loading = True
        
        # Temporarily hide slider during loading to prevent layout interference
        if hasattr(self, 'slider_container'):
            self.slider_container.setVisible(False)
        
        try:
            # Find all TIFF files
            tiff_files = list(folder_path.glob("*.tiff")) + list(folder_path.glob("*.tif"))
            
            if not tiff_files:
                napari.utils.notifications.show_error("No TIFF files found in selected folder")
                self._cleanup_loading_state()
                return
        except Exception as e:
            napari.utils.notifications.show_error(f"Error scanning folder: {str(e)}")
            self._cleanup_loading_state()
            return
        
        # Clear existing data - remove all layers first to prevent duplicates
        self.viewer.layers.clear()
        
        self.channel_raw_data.clear()
        self.channel_normalized_cache.clear()
        self.channel_adjusted_cache.clear()
        self.channel_max_values.clear()
        self.channel_files.clear()
        self.channel_layers.clear()
        self.adjustment_widgets.clear()
        self.channel_colors.clear()
        self.channel_colormaps.clear()
        # Clean up update timers
        for timer in self._update_timers.values():
            if timer.isActive():
                timer.stop()
        self._update_timers.clear()
        self.channel_combo.clear()
        self.channel_list_widget.clear()
        self.channel_search.clear()
        
        # Clear adjustment widgets - disable layout updates to prevent window resize
        # BUT ensure scroll area and container stay visible
        self.adjustments_container.setUpdatesEnabled(False)  # Disable updates during clearing
        self.main_scroll.setUpdatesEnabled(False)  # Also disable scroll area updates
        # Keep scroll area visible
        self.main_scroll.setVisible(True)
        self.main_scroll_container.setVisible(True)
        self.adjustments_container.setVisible(True)
        
        while self.adjustments_layout.count():
            item = self.adjustments_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Store current window size to prevent resizing (less aggressive approach)
        try:
            main_window = self.viewer.window._qt_window
            if main_window:
                # Only set minimum size, don't lock maximum (allows user to resize if needed)
                current_size = main_window.size()
                if current_size.width() > 0 and current_size.height() > 0:
                    main_window.setMinimumSize(max(800, current_size.width()), max(600, current_size.height()))
        except Exception as e:
            # Silently continue - window size locking is not critical
            pass
        
        # Show progress bar
        self.progress_label.setText("Scanning files...")
        self.progress_label.setVisible(True)
        self.progress_bar.setVisible(True)
        # Set initial maximum to file count (will be updated when we know total channels)
        # This ensures progress updates correctly during file scanning
        self.progress_bar.setMaximum(len(tiff_files))
        self.progress_bar.setValue(0)
        # Minimal processEvents - only for progress bar
        QApplication.processEvents()
        
        # First pass: Just register files and create widgets (BATCHED - no layout updates)
        sorted_files = sorted(tiff_files)
        self.channel_list = []  # Reset channel list
        widgets_to_add = []  # Batch widgets to add
        
        # Generate default colors for channels (distinct colors)
        default_colors = [
            QColor(255, 0, 0),      # Red
            QColor(0, 255, 0),      # Green
            QColor(0, 0, 255),      # Blue
            QColor(255, 255, 0),   # Yellow
            QColor(255, 0, 255),   # Magenta
            QColor(0, 255, 255),   # Cyan
            QColor(255, 128, 0),   # Orange
            QColor(128, 0, 255),   # Purple
            QColor(255, 192, 203), # Pink
            QColor(128, 255, 0),   # Lime
        ]
        
        for idx, tiff_file in enumerate(sorted_files):
            channel_name = tiff_file.stem
            self.channel_files[channel_name] = tiff_file
            self.channel_combo.addItem(channel_name)
            self.channel_list.append(channel_name)  # Add to ordered list
            
            # Assign default color (cycle through colors)
            default_color = default_colors[idx % len(default_colors)]
            self.channel_colors[channel_name] = default_color
            # Create custom colormap for this channel
            self.channel_colormaps[channel_name] = self._create_colormap_from_color(default_color)
            
            # Create adjustment widget with callbacks
            def make_visibility_func(ch_name):
                return lambda state: self.toggle_channel_visibility(ch_name, state)
            
            def make_overlay_func(ch_name):
                return lambda state: self.toggle_channel_overlay(ch_name, state)
            
            def make_color_func(ch_name):
                return lambda color: self.update_channel_color(ch_name, color)
            
            adj_widget = ChannelAdjustmentWidget(
                channel_name, 
                visibility_callback=make_visibility_func(channel_name),
                overlay_callback=make_overlay_func(channel_name),
                color_callback=make_color_func(channel_name)
            )
            # Set the default color
            adj_widget.set_color(default_color)
            self.adjustment_widgets[channel_name] = adj_widget
            
            # Connect adjustment signals with debouncing for performance
            def make_update_func(ch_name):
                def debounced_update():
                    # Use a timer to debounce rapid updates
                    if ch_name not in self._update_timers:
                        timer = QTimer()
                        timer.setSingleShot(True)
                        # Use a closure to capture ch_name properly
                        def update_func():
                            self.update_channel_display(ch_name)
                        timer.timeout.connect(update_func)
                        self._update_timers[ch_name] = timer
                    else:
                        timer = self._update_timers[ch_name]
                        timer.stop()  # Reset timer on new change
                    # Delay update by 150ms to batch rapid changes
                    timer.start(150)
                return debounced_update
            
            for spinbox in [adj_widget.brightness_spinbox, adj_widget.contrast_spinbox, 
                           adj_widget.gamma_spinbox, adj_widget.min_spinbox, adj_widget.max_spinbox]:
                spinbox.valueChanged.connect(make_update_func(channel_name))
            
            # Store widget to add later (batch addition)
            widgets_to_add.append(adj_widget)
            # Update progress during file scanning phase
            # Note: Maximum will be updated later when we know total channels
            if hasattr(self, 'progress_bar') and self.progress_bar.isVisible():
                # Progress is 0 to len(sorted_files) for file scanning
                self.progress_bar.setValue(idx + 1)
            
            # Minimal processEvents - only update progress, no layout
            if (idx + 1) % 10 == 0:  # Less frequent updates
                self.progress_label.setText(f"Registering channels... {idx + 1}/{len(sorted_files)}")
                QApplication.processEvents()
        
        # Batch add all widgets at once - this prevents multiple layout recalculations
        try:
            self.adjustments_container.setUpdatesEnabled(False)  # Disable updates during batch add
            self.main_scroll.setUpdatesEnabled(False)  # Also disable scroll area
            for adj_widget in widgets_to_add:
                self.adjustments_layout.addWidget(adj_widget)
            
            # Re-enable updates
            self.adjustments_container.setUpdatesEnabled(True)
            self.main_scroll.setUpdatesEnabled(True)
            
            # Clear search field and reset filter BEFORE showing widgets
            self.channel_search.blockSignals(True)
            self.channel_search.clear()
            self.channel_search.blockSignals(False)
            
            # Show all widgets - they should be visible by default
            for adj_widget in widgets_to_add:
                adj_widget.setVisible(True)
            
            # Ensure scroll area and container are visible
            self.main_scroll.setVisible(True)
            self.main_scroll_container.setVisible(True)
            self.adjustments_container.setVisible(True)
            
            # Reset filter to show all widgets
            self.filter_channels("")
            
            # Update container size to ensure proper scrolling - use delayed update to ensure layout is complete
            # Immediate update
            self._update_scroll_area()
            # Ensure scrollbar is visible
            self._ensure_scrollbar_visible()
            # Delayed updates to catch any delayed layout changes
            QTimer.singleShot(100, lambda: (self._update_scroll_area(), self._ensure_scrollbar_visible()))
            QTimer.singleShot(300, lambda: (self._update_scroll_area(), self._ensure_scrollbar_visible()))
            
            # Single processEvents call for UI update
            QApplication.processEvents()
        except Exception as e:
            # If widget addition fails, at least ensure UI is usable
            napari.utils.notifications.show_warning(f"Warning: Some widgets may not be visible. Error: {str(e)}")
            self.adjustments_container.setUpdatesEnabled(True)
            self.adjustments_scroll.setUpdatesEnabled(True)
        
        # Second pass: Load all channels (not just preview)
        channel_names_list = list(self.channel_files.keys())
        num_sorted_files = len(sorted_files)
        total_operations = num_sorted_files + len(channel_names_list)
        
        # Update progress bar maximum to include both file scanning and channel loading
        self.progress_bar.setMaximum(total_operations)
        # Set current progress to file scanning complete
        self.progress_bar.setValue(num_sorted_files)
        
        self.progress_label.setText(f"Loading all channels...")
        QApplication.processEvents()
        
        # Load all channels with error handling
        qt_viewer = None
        main_window = None
        try:
            qt_viewer = self.viewer.window.qt_viewer
            main_window = self.viewer.window._qt_window
        except:
            pass
        
        loaded_count = 0
        for idx, channel_name in enumerate(channel_names_list):
            try:
                self.progress_label.setText(f"Loading channel {idx + 1}/{len(channel_names_list)}: {channel_name}")
                # Update progress before loading (shows we're starting this channel)
                current_progress = num_sorted_files + idx
                self.progress_bar.setValue(current_progress)
                QApplication.processEvents()  # Update UI immediately
                
                self._load_channel_data(channel_name)
                self.load_channel(channel_name)
                loaded_count += 1
                
                # Update progress after loading (shows this channel is complete)
                self.progress_bar.setValue(num_sorted_files + idx + 1)
                
                # Periodic UI update for progress
                if (idx + 1) % 5 == 0:
                    QApplication.processEvents()
            except Exception as e:
                napari.utils.notifications.show_warning(f"Failed to load channel {channel_name}: {str(e)}")
                # Still update progress even if loading failed
                self.progress_bar.setValue(num_sorted_files + idx + 1)
                continue
        
        # Hide progress indicators
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        
        # Re-enable button
        self.load_btn.setEnabled(True)
        self.load_btn.setText("Load MIBI Folder")
        
        # Always clear loading flag, even if there are errors
        self._cleanup_loading_state()
        
        # Update channel slider
        if len(self.channel_list) > 0:
            try:
                self.channel_slider.setMaximum(len(self.channel_list) - 1)
                self.channel_slider.setValue(0)
                self.update_slider_label()
                
                # Update channel list widget for quick navigation
                self.channel_list_widget.clear()
                for channel_name in self.channel_list:
                    item = QListWidgetItem(channel_name)
                    self.channel_list_widget.addItem(item)
                
                # Ensure adjustment widgets are visible
                self._ensure_widgets_visible()
            except Exception as e:
                napari.utils.notifications.show_warning(f"Error updating UI: {str(e)}")
        
        # Single UI update
        QApplication.processEvents()
        
        # Ensure slider overlay is properly set up after loading
        try:
            if not hasattr(self, 'slider_container') or self.slider_container.parent() is None:
                self._setup_slider_overlay()
            
            # Update slider state after loading channels
            self.update_slider_state()
            
            # Show slider with single delayed update
            if hasattr(self, 'slider_container'):
                self.slider_container.setVisible(True)
                QTimer.singleShot(200, lambda: self._debounced_update_slider_position())
        except Exception as e:
            # Slider setup is not critical - continue without it
            pass
        
        # If in single channel mode, show the first channel and make slider enabled
        if self.single_channel_active:
            try:
                self.channel_slider.setEnabled(True)
                self.show_single_channel()
            except:
                pass
        
        if self.channel_combo.count() > 0:
            self.channel_combo.setCurrentIndex(0)
        
        # Restore window size constraints after a delay
        QTimer.singleShot(200, lambda: self._restore_window_constraints())
        
        # Show completion notification
        try:
            napari.utils.notifications.show_info(
                f"Registered {len(self.channel_files)} channels from {self.current_folder.name}. "
                f"Loaded {loaded_count} channels."
            )
        except:
            pass
    
    def _cleanup_loading_state(self):
        """Clean up loading state - ensure UI is restored"""
        self._is_loading = False
        self.load_btn.setEnabled(True)
        self.load_btn.setText("Load MIBI Folder")
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
    
    def _update_scroll_area(self):
        """Update main scroll area to reflect current content size and ensure scrollbar appears"""
        try:
            # Process any pending layout updates first
            QApplication.processEvents()
            
            # Force all widgets in main scroll layout to update their geometry
            for i in range(self.main_scroll_layout.count()):
                item = self.main_scroll_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    widget.updateGeometry()
                    widget.adjustSize()
            
            # Force adjustment widgets to update
            for i in range(self.adjustments_layout.count()):
                item = self.adjustments_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    widget.updateGeometry()
                    widget.adjustSize()
            
            # Force main container to recalculate its size based on content
            self.main_scroll_container.updateGeometry()
            self.main_scroll_container.adjustSize()
            
            # Get viewport size
            viewport = self.main_scroll.viewport()
            viewport_width = viewport.width() if viewport else 300
            viewport_height = viewport.height() if viewport else 600
            
            # Set main container width to match viewport (scrollbar width will be accounted for automatically)
            if viewport_width > 0:
                self.main_scroll_container.setMinimumWidth(viewport_width)
                # Don't set maximum width - allow container to expand with content
            
            # Calculate total height needed for all widgets in main scroll layout
            total_height = 0
            for i in range(self.main_scroll_layout.count()):
                item = self.main_scroll_layout.itemAt(i)
                if item and item.widget() and item.widget().isVisible():
                    widget = item.widget()
                    widget.updateGeometry()
                    widget.adjustSize()
                    widget_height = widget.sizeHint().height()
                    if widget_height <= 0:
                        widget_height = widget.minimumSizeHint().height()
                    if widget_height > 0:
                        total_height += widget_height + self.main_scroll_layout.spacing()
            
            # Add layout margins
            margins = self.main_scroll_layout.contentsMargins()
            total_height += margins.top() + margins.bottom()
            
            # Use calculated height or fallback to size hint
            if total_height <= 0:
                container_size_hint = self.main_scroll_container.sizeHint()
                total_height = container_size_hint.height() if container_size_hint.height() > 0 else self.main_scroll_container.minimumSizeHint().height()
            
            # Set main container height to its content height - this will trigger scrollbar when > viewport
            if total_height > 0:
                self.main_scroll_container.setMinimumHeight(total_height)
                # Resize container to its preferred size
                self.main_scroll_container.resize(viewport_width, total_height)
            
            # Update scroll area to recognize new content size
            self.main_scroll.updateGeometry()
            
            # Force scroll area to check if scrollbar is needed and ensure it's visible
            scroll_range = max(0, total_height - viewport_height)
            
            # Set scrollbar range - this will make scrollbar appear when range > 0
            scrollbar = self.main_scroll.verticalScrollBar()
            scrollbar.setRange(0, scroll_range)
            
            # Ensure scrollbar is always visible on the right side
            self.main_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            
            # Always keep scrollbar visible and enabled
            scrollbar.setVisible(True)
            scrollbar.setEnabled(True)
            scrollbar.show()  # Explicitly show scrollbar
            
        except Exception as e:
            pass
    
    def _ensure_scrollbar_visible(self):
        """Ensure the vertical scrollbar is always visible on the main scroll panel"""
        try:
            scrollbar = self.main_scroll.verticalScrollBar()
            # Force scrollbar to always be visible
            self.main_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            scrollbar.setVisible(True)
            scrollbar.setEnabled(True)
            scrollbar.show()
            
            # Update container size to ensure scrollbar appears
            self._update_scroll_area()
        except Exception as e:
            # Fallback: just do basic update
            try:
                self.main_scroll_container.updateGeometry()
                self.main_scroll_container.adjustSize()
                self.main_scroll.updateGeometry()
            except:
                pass
    
    def _ensure_widgets_visible(self):
        """Ensure adjustment widgets are visible - simplified version"""
        try:
            # Ensure scroll area and container are visible
            self.main_scroll.setVisible(True)
            self.main_scroll_container.setVisible(True)
            self.adjustments_container.setVisible(True)
            
            # Clear search and reset filter to show all widgets
            if hasattr(self, 'channel_search'):
                self.channel_search.blockSignals(True)
                self.channel_search.clear()
                self.channel_search.blockSignals(False)
            
            # Ensure all adjustment widgets are visible
            for i in range(self.adjustments_layout.count()):
                item = self.adjustments_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    if isinstance(widget, ChannelAdjustmentWidget):
                        widget.setVisible(True)
            
            # Reset filter to show all widgets
            self.filter_channels("")
            
            # Update scroll area after visibility changes
            self._update_scroll_area()
        except Exception as e:
            # Non-critical - continue even if visibility update fails
            pass
    
    def _restore_window_constraints(self):
        """Restore window size constraints after loading"""
        try:
            main_window = self.viewer.window._qt_window
            if main_window:
                # Remove aggressive size constraints
                main_window.setMinimumSize(0, 0)
                main_window.setMaximumSize(16777215, 16777215)
                
                # Restore scroll area size constraints - main scroll should expand to fill space
                self.main_scroll.setMinimumWidth(300)
                self.main_scroll.setMaximumWidth(16777215)
                # Ensure container can expand horizontally
                self.main_scroll_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
                
                # Ensure widgets are visible
                self._ensure_widgets_visible()
        except Exception as e:
            # Non-critical - continue even if constraint restoration fails
            pass
    
    def _load_channel_data(self, channel_name: str):
        """Load raw image data for a channel (lazy loading)"""
        if channel_name in self.channel_raw_data:
            return  # Already loaded
        
        if channel_name not in self.channel_files:
            return
        
        try:
            # Load raw image
            img = tifffile.imread(str(self.channel_files[channel_name]))
            
            # Process events periodically during large image loading
            if img.size > 1000000:  # For large images
                QApplication.processEvents()
            
            # Store raw data and compute max value for normalization
            self.channel_raw_data[channel_name] = img
            max_val = float(img.max()) if img.size > 0 else 1.0
            self.channel_max_values[channel_name] = max_val if max_val > 0 else 1.0
            
            # Normalize and cache (use efficient operations)
            if img.dtype != np.float32 and img.dtype != np.float64:
                img_normalized = img.astype(np.float32, copy=False)
                if max_val > 1.0:
                    img_normalized = np.divide(img_normalized, self.channel_max_values[channel_name], 
                                             out=img_normalized, casting='unsafe')
            else:
                if max_val > 1.0:
                    img_normalized = img / self.channel_max_values[channel_name]
                else:
                    img_normalized = img
            
            self.channel_normalized_cache[channel_name] = img_normalized
            
        except Exception as e:
            # Show user-friendly error message
            napari.utils.notifications.show_error(f"Error loading channel {channel_name}: {str(e)}")
            print(f"Error loading {channel_name}: {e}")
    
    def load_channel(self, channel_name: str):
        """Load a channel into the viewer"""
        # Lazy load data if not already loaded
        if channel_name not in self.channel_raw_data:
            self._load_channel_data(channel_name)
        
        if channel_name not in self.channel_normalized_cache:
            return
        
        # Check if layer already exists in napari (by name) - prevent duplicates
        existing_layer = None
        duplicate_layers = []
        for layer in self.viewer.layers:
            # Check exact match or name with [number] suffix
            layer_name = layer.name
            # Extract base name if it has [number] suffix
            if ' [' in layer_name and layer_name.endswith(']'):
                base_name = layer_name.split(' [')[0]
            else:
                base_name = layer_name
            
            if base_name == channel_name:
                if existing_layer is None:
                    existing_layer = layer
                else:
                    # Found a duplicate - mark for removal
                    duplicate_layers.append(layer)
        
        # Remove duplicate layers immediately
        for dup_layer in duplicate_layers:
            if dup_layer in self.viewer.layers:
                self.viewer.layers.remove(dup_layer)
        
        # Get normalized image from cache
        img = self.channel_normalized_cache[channel_name]
        
        # Apply adjustments
        adjusted_img = self.apply_adjustments(channel_name, img)
        
        # Get color and overlay state for layer creation/update
        channel_color = self.channel_colors.get(channel_name, QColor(255, 255, 255))
        overlay_enabled = True
        if channel_name in self.adjustment_widgets:
            overlay_enabled = self.adjustment_widgets[channel_name].overlay_checkbox.isChecked()
        
        # Determine if we need colored colormap (multichannel mode with overlay) or grayscale
        needs_colored = not self.single_channel_active and overlay_enabled
        
        # Add or update layer
        if channel_name in self.channel_layers:
            # Update existing layer - use colormap instead of RGB
            layer = self.channel_layers[channel_name]
            
            if needs_colored:
                # Use custom colormap for multichannel mode
                custom_colormap = self.channel_colormaps.get(channel_name)
                if custom_colormap is None:
                    custom_colormap = self._create_colormap_from_color(channel_color)
                    self.channel_colormaps[channel_name] = custom_colormap
                layer.colormap = custom_colormap
                layer.data = adjusted_img
                layer.visible = True
            else:
                # Use grayscale colormap for single channel mode
                layer.colormap = 'gray'
                layer.data = adjusted_img
                layer.visible = overlay_enabled if not self.single_channel_active else True
        elif existing_layer is not None:
            # Use existing layer from napari - update colormap
            was_visible = existing_layer.visible
            
            if needs_colored:
                # Use custom colormap for multichannel mode
                custom_colormap = self.channel_colormaps.get(channel_name)
                if custom_colormap is None:
                    custom_colormap = self._create_colormap_from_color(channel_color)
                    self.channel_colormaps[channel_name] = custom_colormap
                existing_layer.colormap = custom_colormap
                existing_layer.data = adjusted_img
                existing_layer.visible = True
            else:
                # Use grayscale colormap
                existing_layer.colormap = 'gray'
                existing_layer.data = adjusted_img
                existing_layer.visible = was_visible
            
            existing_layer.name = channel_name
            self.channel_layers[channel_name] = existing_layer
            # Sync visibility checkbox
            if channel_name in self.adjustment_widgets:
                self.adjustment_widgets[channel_name].visible_checkbox.setChecked(existing_layer.visible)
        else:
            # Create new layer - disable canvas updates during loading to prevent resize
            if self._is_loading:
                try:
                    qt_viewer = self.viewer.window.qt_viewer
                    if qt_viewer:
                        qt_viewer.setUpdatesEnabled(False)
                except:
                    pass
            
            # In multichannel mode with overlay enabled, use custom colormap
            if needs_colored:
                # Use custom colormap for multichannel mode
                custom_colormap = self.channel_colormaps.get(channel_name)
                if custom_colormap is None:
                    custom_colormap = self._create_colormap_from_color(channel_color)
                    self.channel_colormaps[channel_name] = custom_colormap
                
                layer = self.viewer.add_image(
                    adjusted_img,
                    name=channel_name,
                    colormap=custom_colormap,
                    blending='additive',
                    opacity=1.0
                )
            else:
                # Single channel mode or overlay disabled - use grayscale
                layer = self.viewer.add_image(
                    adjusted_img,
                    name=channel_name,
                    colormap='gray',
                    blending='additive',
                    visible=overlay_enabled if not self.single_channel_active else True
                )
            self.channel_layers[channel_name] = layer
            
            # Re-enable updates if we disabled them
            if self._is_loading:
                try:
                    if qt_viewer:
                        qt_viewer.setUpdatesEnabled(True)
                except:
                    pass
            
            # Sync visibility checkbox
            if channel_name in self.adjustment_widgets:
                self.adjustment_widgets[channel_name].visible_checkbox.setChecked(layer.visible)
    
    def _create_colormap_from_color(self, color: QColor) -> Colormap:
        """Create a custom colormap from a QColor for grayscale to color mapping"""
        # Create a colormap that maps grayscale (0-1) to the specified color
        # Use a simple linear colormap from black to the specified color
        colors = np.array([
            [0.0, 0.0, 0.0, 1.0],  # Black at 0
            [color.red() / 255.0, color.green() / 255.0, color.blue() / 255.0, 1.0]  # Color at 1
        ])
        return Colormap(colors=colors, name=f"custom_{color.name()}")
    
    def apply_adjustments(self, channel_name: str, img: np.ndarray) -> np.ndarray:
        """Apply brightness, contrast, and gamma adjustments to an image (optimized)"""
        if channel_name not in self.adjustment_widgets:
            return img
        
        adj = self.adjustment_widgets[channel_name].get_adjustments()
        
        # Check if adjustments are default (no changes needed)
        if (adj['brightness'] == 0.0 and adj['contrast'] == 1.0 and 
            adj['gamma'] == 1.0 and adj['min'] == 0.0 and adj['max'] == 1.0):
            return img
        
        # Use cached result if available and adjustments haven't changed
        # (For now, we'll recompute, but could add caching with adjustment hash)
        
        # Work on a copy (required for napari)
        result = img.copy()
        
        # Apply brightness (additive) - in-place where possible
        if adj['brightness'] != 0.0:
            result += adj['brightness']
        
        # Apply contrast (multiplicative around 0.5)
        if adj['contrast'] != 1.0:
            result -= 0.5
            result *= adj['contrast']
            result += 0.5
        
        # Apply gamma correction (only if not 1.0)
        if adj['gamma'] != 1.0:
            np.clip(result, 0, 1, out=result)
            np.power(result, 1.0 / adj['gamma'], out=result)
        
        # Apply display range (min/max)
        if adj['min'] != 0.0 or adj['max'] != 1.0:
            range_size = adj['max'] - adj['min']
            if range_size > 1e-10:
                result -= adj['min']
                result /= range_size
            else:
                result.fill(0.0)
        
        # Clip to valid range
        np.clip(result, 0, 1, out=result)
        
        return result
    
    def update_channel_display(self, channel_name: str):
        """Update the display of a channel with current adjustments and color (optimized)"""
        # Only update if channel is loaded
        if channel_name not in self.channel_layers:
            return
        
        if channel_name not in self.channel_normalized_cache:
            # Lazy load if not loaded
            self._load_channel_data(channel_name)
            if channel_name not in self.channel_normalized_cache:
                return
        
        img = self.channel_normalized_cache[channel_name]
        adjusted_img = self.apply_adjustments(channel_name, img)
        
        layer = self.channel_layers[channel_name]
        
        # Get color and overlay state
        channel_color = self.channel_colors.get(channel_name, QColor(255, 255, 255))
        overlay_enabled = True
        if channel_name in self.adjustment_widgets:
            overlay_enabled = self.adjustment_widgets[channel_name].overlay_checkbox.isChecked()
        
        needs_colored = not self.single_channel_active and overlay_enabled
        
        # Update layer data and colormap directly (much faster than recreating)
        try:
            # Update data directly - this is much faster than recreating the layer
            layer.data = adjusted_img
            
            # Update colormap if needed
            if needs_colored:
                custom_colormap = self.channel_colormaps.get(channel_name)
                if custom_colormap is None:
                    custom_colormap = self._create_colormap_from_color(channel_color)
                    self.channel_colormaps[channel_name] = custom_colormap
                layer.colormap = custom_colormap
            else:
                layer.colormap = 'gray'
        except Exception as e:
            # If direct update fails, fall back to reloading (slower but more reliable)
            try:
                was_visible = layer.visible
                self.viewer.layers.remove(layer)
                del self.channel_layers[channel_name]
                self.load_channel(channel_name)
                if channel_name in self.channel_layers:
                    self.channel_layers[channel_name].visible = was_visible
            except Exception as e2:
                # Log error but don't crash
                print(f"Error updating channel {channel_name}: {e2}")
    
    def on_channel_selected(self, channel_name: str):
        """Handle channel selection from combo box - scroll to the adjustment widget and select layer"""
        if not channel_name or self._updating_selection:
            return
        
        # If in single channel mode, update slider instead
        if self.single_channel_active:
            if channel_name in self.channel_list:
                idx = self.channel_list.index(channel_name)
                self.channel_slider.setValue(idx)
            return
            
        # Load channel if not already loaded
        if channel_name not in self.channel_layers:
            self.load_channel(channel_name)
        
        # Select the layer in napari
        if channel_name in self.channel_layers:
            self._updating_selection = True
            try:
                self.viewer.layers.selection.active = self.channel_layers[channel_name]
            finally:
                self._updating_selection = False
        
        # Scroll to the adjustment widget
        if channel_name in self.adjustment_widgets:
            widget = self.adjustment_widgets[channel_name]
            # Scroll to the selected widget
            scroll_area = widget.parent().parent()  # Get the scroll area
            if isinstance(scroll_area, QScrollArea):
                scroll_area.ensureWidgetVisible(widget)
    
    def update_view_mode_button_text(self):
        """Update the view mode button - dim inactive mode instead of checkmark"""
        if hasattr(self, 'single_channel_label') and hasattr(self, 'multi_channel_label'):
            if self.single_channel_active:
                # Single channel active - highlight it, dim multi-channel
                self.single_channel_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-weight: 700;
                        font-size: 11pt;
                        background: transparent;
                        border: none;
                    }
                """)
                self.multi_channel_label.setStyleSheet("""
                    QLabel {
                        color: rgba(150, 150, 150, 200);
                        font-weight: 500;
                        font-size: 11pt;
                        background: transparent;
                        border: none;
                    }
                """)
            else:
                # Multi-channel active - highlight it, dim single channel
                self.single_channel_label.setStyleSheet("""
                    QLabel {
                        color: rgba(150, 150, 150, 200);
                        font-weight: 500;
                        font-size: 11pt;
                        background: transparent;
                        border: none;
                    }
                """)
                self.multi_channel_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-weight: 700;
                        font-size: 11pt;
                        background: transparent;
                        border: none;
                    }
                """)
    
    def update_slider_state(self):
        """Update slider enabled/disabled state and visual appearance"""
        if not hasattr(self, 'channel_slider'):
            return
        
        is_enabled = self.single_channel_active and len(self.channel_list) > 0
        self.channel_slider.setEnabled(is_enabled)
        
        # Update label to show current state
        if is_enabled:
            self.channel_label.setText("Channel:")
            self.channel_label.setStyleSheet("""
                QLabel {
                    color: #D0D0D0;
                    font-weight: 600;
                    font-size: 13px;
                    padding: 2px 0px;
                }
            """)
        else:
            self.channel_label.setText("Channel: (Multi-Channel Mode)")
            self.channel_label.setStyleSheet("""
                QLabel {
                    color: #888888;
                    font-weight: 500;
                    font-size: 12px;
                    padding: 2px 0px;
                    font-style: italic;
                }
            """)
        
        # Update slider label styling
        if is_enabled:
            self.channel_slider_label.setStyleSheet("""
                QLabel {
                    background: rgba(40, 40, 45, 200);
                    color: #FFFFFF;
                    font-weight: 700;
                    font-size: 13px;
                    padding: 6px 12px;
                    border-radius: 6px;
                    border: 1px solid rgba(100, 100, 110, 200);
                }
            """)
        else:
            self.channel_slider_label.setStyleSheet("""
                QLabel {
                    background: rgba(30, 30, 35, 200);
                    color: #888888;
                    font-weight: 500;
                    font-size: 12px;
                    padding: 6px 12px;
                    border-radius: 6px;
                    border: 1px solid rgba(60, 60, 70, 150);
                }
            """)
    
    def toggle_single_channel_mode_btn(self):
        """Toggle single channel viewing mode (button version) - optimized for smooth switching"""
        # Disable button temporarily to prevent multiple clicks
        self.single_channel_mode_btn.setEnabled(False)
        
        try:
            # Toggle the state
            self.single_channel_active = not self.single_channel_active
            
            # Ensure slider overlay exists and is properly configured
            if not hasattr(self, 'slider_container') or self.slider_container.parent() is None:
                self._setup_slider_overlay()
            
            # Update slider state (enabled/disabled) - slider is always visible now
            self.update_slider_state()
            
            # Ensure slider overlay is visible and properly positioned
            if hasattr(self, 'slider_container'):
                # Force visibility FIRST before any other operations
                self.slider_container.setVisible(True)
                self.slider_container.show()
                
                # Use debounced update to prevent layout thrashing
                self._debounced_update_slider_position()
            
            # Update button text immediately for visual feedback
            self.update_view_mode_button_text()
            QApplication.processEvents()
            
            if self.single_channel_active:
                # Store current visibility state before switching
                self.previous_visibility_state = {
                    name: layer.visible 
                    for name, layer in self.channel_layers.items()
                }
                # Show only the current channel from slider
                self.show_single_channel()
            else:
                # Restore previous visibility state
                self.restore_multi_channel_view()
        finally:
            # Re-enable button
            self.single_channel_mode_btn.setEnabled(True)
    
    def toggle_single_channel_mode(self, state: int):
        """Toggle single channel viewing mode (checkbox version - for compatibility)"""
        checked = (state == Qt.Checked)
        self.single_channel_active = checked
        self.channel_slider.setEnabled(self.single_channel_active)
        
        # Sync button text
        if hasattr(self, 'single_channel_mode_btn'):
            self.update_view_mode_button_text()
        
        if self.single_channel_active:
            # Show only the current channel from slider
            self.show_single_channel()
        else:
            # Show all currently visible channels
            # (Don't automatically show all, just restore previous state)
            pass
    
    def show_single_channel(self):
        """Show only the channel selected by the slider - optimized"""
        if not self.single_channel_active or len(self.channel_list) == 0:
            return
        
        current_idx = self.channel_slider.value()
        if current_idx < 0 or current_idx >= len(self.channel_list):
            return
        
        current_channel = self.channel_list[current_idx]
        
        # Batch hide operations - faster approach
        layers_to_hide = []
        widgets_to_update = []
        
        for channel_name, layer in self.channel_layers.items():
            if channel_name != current_channel:
                if layer.visible:
                    layers_to_hide.append(layer)
                    if channel_name in self.adjustment_widgets:
                        widgets_to_update.append(self.adjustment_widgets[channel_name].visible_checkbox)
        
        # Hide all layers at once (faster)
        for layer in layers_to_hide:
            layer.visible = False
        
        # Update checkboxes without triggering signals (faster)
        for checkbox in widgets_to_update:
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
        
        QApplication.processEvents()
        
        # Load and show the selected channel
        if current_channel not in self.channel_layers:
            self.load_channel(current_channel)
            QApplication.processEvents()
        
        if current_channel in self.channel_layers:
            layer = self.channel_layers[current_channel]
            if not layer.visible:
                layer.visible = True
            if current_channel in self.adjustment_widgets:
                self.adjustment_widgets[current_channel].visible_checkbox.setChecked(True)
            
            # Select the layer
            self._updating_selection = True
            try:
                self.viewer.layers.selection.active = layer
                # Update combo box
                index = self.channel_combo.findText(current_channel)
                if index >= 0 and self.channel_combo.currentIndex() != index:
                    self.channel_combo.setCurrentIndex(index)
            finally:
                self._updating_selection = False
        
        self.update_slider_label()
        QApplication.processEvents()
    
    def restore_multi_channel_view(self):
        """Restore multi-channel view - respect overlay checkboxes"""
        # Update all channels based on overlay checkbox state
        for channel_name in self.channel_layers.keys():
            if channel_name in self.adjustment_widgets:
                overlay_enabled = self.adjustment_widgets[channel_name].overlay_checkbox.isChecked()
                # Update display to apply color if overlay is enabled
                self.update_channel_display(channel_name)
                # Set visibility based on overlay checkbox
                self.channel_layers[channel_name].visible = overlay_enabled
                # Sync visibility checkbox
                checkbox = self.adjustment_widgets[channel_name].visible_checkbox
                checkbox.blockSignals(True)
                checkbox.setChecked(overlay_enabled)
                checkbox.blockSignals(False)
        
        QApplication.processEvents()
    
    def on_slider_changed(self, value: int):
        """Handle channel slider change - optimized for smooth sliding"""
        if not self.single_channel_active:
            return
        
        # Update label immediately for visual feedback
        self.update_slider_label()
        QApplication.processEvents()
        
        # Show the channel
        self.show_single_channel()
    
    def update_slider_label(self):
        """Update the slider label showing current channel number"""
        if len(self.channel_list) == 0:
            self.channel_slider_label.setText("0/0")
        else:
            current_idx = self.channel_slider.value()
            total = len(self.channel_list)
            if 0 <= current_idx < len(self.channel_list):
                channel_name = self.channel_list[current_idx]
                # Truncate long channel names
                display_name = channel_name[:15] + "..." if len(channel_name) > 15 else channel_name
                self.channel_slider_label.setText(f"{current_idx + 1}/{total}")
                self.channel_slider_label.setToolTip(channel_name)  # Full name in tooltip
            else:
                self.channel_slider_label.setText(f"{current_idx + 1}/{total}")
    
    def show_all_channels(self):
        """Show all channels (with lazy loading) - respect overlay checkboxes in multichannel mode"""
        # If in single channel mode, disable it first
        if self.single_channel_active:
            if hasattr(self, 'single_channel_mode_btn'):
                self.single_channel_mode_btn.setEnabled(True)  # Make sure it's enabled
                self.single_channel_active = False
                self.channel_slider.setEnabled(False)
                self.update_view_mode_button_text()
                self.restore_multi_channel_view()
        
        for channel_name in self.channel_files.keys():
            # Load if not already loaded
            if channel_name not in self.channel_layers:
                self.load_channel(channel_name)
            
            # In multichannel mode, respect overlay checkbox; in single channel mode, show all
            if not self.single_channel_active:
                # Multichannel mode - check overlay checkbox
                if channel_name in self.adjustment_widgets:
                    overlay_enabled = self.adjustment_widgets[channel_name].overlay_checkbox.isChecked()
                    if channel_name in self.channel_layers:
                        self.channel_layers[channel_name].visible = overlay_enabled
                    self.adjustment_widgets[channel_name].visible_checkbox.setChecked(overlay_enabled)
                    # Update display to apply color
                    self.update_channel_display(channel_name)
            else:
                # Single channel mode - show all
                if channel_name in self.channel_layers:
                    self.channel_layers[channel_name].visible = True
                if channel_name in self.adjustment_widgets:
                    self.adjustment_widgets[channel_name].visible_checkbox.setChecked(True)
    
    def hide_all_channels(self):
        """Hide all channels"""
        for layer in self.channel_layers.values():
            layer.visible = False
        # Update checkboxes
        for channel_name, widget in self.adjustment_widgets.items():
            if channel_name in self.channel_layers:
                widget.visible_checkbox.setChecked(False)
    
    def toggle_channel_visibility(self, channel_name: str, state: int):
        """Toggle visibility of a specific channel (with lazy loading)"""
        # If in single channel mode, don't allow manual visibility toggles
        if self.single_channel_active:
            # Update slider to this channel instead
            if channel_name in self.channel_list:
                idx = self.channel_list.index(channel_name)
                self.channel_slider.setValue(idx)
            return
        
        is_visible = (state == Qt.Checked)
        
        if is_visible:
            # Load channel if not already loaded
            if channel_name not in self.channel_layers:
                self.load_channel(channel_name)
            elif channel_name in self.channel_layers:
                self.channel_layers[channel_name].visible = True
        else:
            # Just hide if already loaded
            if channel_name in self.channel_layers:
                self.channel_layers[channel_name].visible = False
    
    def toggle_channel_overlay(self, channel_name: str, state: int):
        """Toggle overlay state of a channel in multichannel mode"""
        if self.single_channel_active:
            return  # Overlay only matters in multichannel mode
        
        is_overlay = (state == Qt.Checked)
        
        if channel_name in self.channel_layers:
            layer = self.channel_layers[channel_name]
            if is_overlay:
                # Enable overlay - reload with color
                self.update_channel_display(channel_name)
                layer.visible = True
            else:
                # Disable overlay - hide layer
                layer.visible = False
    
    def update_channel_color(self, channel_name: str, color: QColor):
        """Update the color assigned to a channel"""
        self.channel_colors[channel_name] = color
        # Update colormap
        self.channel_colormaps[channel_name] = self._create_colormap_from_color(color)
        
        # If channel is loaded and in multichannel mode, update the display
        if not self.single_channel_active and channel_name in self.channel_layers:
            self.update_channel_display(channel_name)
    
    def reset_all_channels(self):
        """Reset all channel adjustments"""
        try:
            for widget in self.adjustment_widgets.values():
                widget.reset()
            
            # Reload all visible channels
            for channel_name in self.channel_layers.keys():
                self.update_channel_display(channel_name)
            
            napari.utils.notifications.show_info("All channels have been reset to default values")
        except Exception as e:
            napari.utils.notifications.show_error(f"Error resetting channels: {str(e)}")
    
    def show_panel_info(self):
        """Show information about panel differences"""
        info_text = """
        <h3>Panel Differences:</h3>
        
        <b>Left Panel (Napari Layer List):</b>
        <ul>
        <li>Built-in napari layer management</li>
        <li>Basic layer visibility toggle (eye icon)</li>
        <li>Layer selection and ordering</li>
        <li>Layer properties (opacity, blending, colormap)</li>
        <li>Quick layer navigation</li>
        </ul>
        
        <b>Right Panel (Adjustment Controls):</b>
        <ul>
        <li><b>FIJI-style adjustments:</b> Brightness, Contrast, Gamma</li>
        <li><b>Display Range:</b> Min/Max value controls</li>
        <li><b>Per-channel controls:</b> Each channel has its own sliders</li>
        <li><b>Search function:</b> Quickly find channels by name</li>
        <li><b>Quick select list:</b> Fast channel navigation</li>
        <li><b>Collapsible widgets:</b> Click channel name to collapse/expand</li>
        <li><b>Real-time updates:</b> See changes instantly</li>
        </ul>
        
        <b>Tip:</b> Use the search box to quickly find channels when you have 30+ channels!
        """
        
        msg = QMessageBox()
        msg.setWindowTitle("Panel Information")
        msg.setTextFormat(Qt.RichText)
        msg.setText(info_text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
    
    def on_layer_added(self, event):
        """Handle layer addition - check for duplicates"""
        new_layer = event.value
        if new_layer is None:
            return
        
        layer_name = new_layer.name
        # Extract base name if it has [number] suffix
        if ' [' in layer_name and layer_name.endswith(']'):
            channel_name = layer_name.split(' [')[0]
        else:
            channel_name = layer_name
        
        # If this layer is for a channel we manage
        if channel_name in self.channel_files:
            # Check if we already have this channel
            if channel_name in self.channel_layers:
                existing_layer = self.channel_layers[channel_name]
                # If it's a different layer, remove the duplicate
                if existing_layer != new_layer:
                    # Remove the duplicate
                    if new_layer in self.viewer.layers:
                        self.viewer.layers.remove(new_layer)
            else:
                # Register this layer
                if layer_name != channel_name:
                    new_layer.name = channel_name
                self.channel_layers[channel_name] = new_layer
    
    def on_layer_removed(self, event):
        """Handle layer removal"""
        pass
    
    def filter_channels(self, search_text: str):
        """Filter channels in the adjustment widgets section (between Find Channel and Global Controls)"""
        search_lower = search_text.lower().strip()
        
        # Filter ONLY the adjustment widgets in the scrollable area (not the quick select list)
        first_visible = None
        visible_count = 0
        
        # Iterate through all adjustment widgets in the layout
        for i in range(self.adjustments_layout.count()):
            item = self.adjustments_layout.itemAt(i)
            if item is None:
                continue
            
            widget = item.widget()
            if widget is None or not isinstance(widget, ChannelAdjustmentWidget):
                continue
            
            channel_name = widget.channel_name
            
            # If search is empty, show all; otherwise filter by name
            if not search_lower or search_lower in channel_name.lower():
                widget.setVisible(True)
                visible_count += 1
                if first_visible is None:
                    first_visible = widget
            else:
                widget.setVisible(False)
        
        # Update container size after visibility changes to ensure proper scrolling
        self._update_scroll_area()
        
        # Auto-scroll to first visible widget in the adjustment panel
        if first_visible and search_text:
            # Process events to ensure visibility changes take effect
            QApplication.processEvents()
            # Use QTimer to ensure scroll happens after widget visibility is updated
            QTimer.singleShot(100, lambda: self.scroll_to_widget(first_visible))
        
        # Keep quick select list visible (don't filter it - it's separate)
        # The search is specifically for the adjustment widgets section
    
    def scroll_to_widget(self, widget):
        """Scroll to a specific widget in the adjustment panel, ensuring full visibility"""
        if widget and self.main_scroll:
            # Expand if collapsed first
            if hasattr(widget, 'is_collapsed') and widget.is_collapsed:
                widget.toggle_collapse()
                QApplication.processEvents()  # Wait for expansion
            
            # Get widget position relative to main scroll container
            widget_pos = widget.mapTo(self.main_scroll_container, widget.rect().topLeft())
            widget_height = widget.height()
            
            # Get scroll area viewport
            viewport = self.main_scroll.viewport()
            viewport_height = viewport.height()
            
            # Calculate scroll position to center the widget or show it fully
            # Try to show the widget centered if it fits, otherwise show from top
            if widget_height <= viewport_height:
                # Widget fits in viewport - center it
                scroll_pos = widget_pos.y() - (viewport_height - widget_height) // 2
            else:
                # Widget is larger than viewport - show from top
                scroll_pos = widget_pos.y()
            
            # Ensure scroll position is valid
            scroll_pos = max(0, scroll_pos)
            
            # Scroll to position
            scroll_bar = self.main_scroll.verticalScrollBar()
            scroll_bar.setValue(scroll_pos)
            
            # Also use ensureWidgetVisible as backup
            self.main_scroll.ensureWidgetVisible(widget, 0, 20)  # 20px margin
    
    def on_channel_list_selected(self, item: QListWidgetItem):
        """Handle channel selection from quick list - jump to adjustment widget"""
        channel_name = item.text()
        
        # Clear search to show all channels
        self.channel_search.clear()
        
        # Scroll to the adjustment widget
        if channel_name in self.adjustment_widgets:
            widget = self.adjustment_widgets[channel_name]
            widget.setVisible(True)
            # Expand if collapsed
            if widget.is_collapsed:
                widget.toggle_collapse()
                QApplication.processEvents()
            
            # Scroll to the widget using our improved scroll function
            QTimer.singleShot(50, lambda: self.scroll_to_widget(widget))
        
        # Update combo box (if still present)
        if hasattr(self, 'channel_combo'):
            index = self.channel_combo.findText(channel_name)
            if index >= 0:
                self.channel_combo.setCurrentIndex(index)
        
        # Load and show channel
        if channel_name not in self.channel_layers:
            self.load_channel(channel_name)
        elif channel_name in self.channel_layers:
            self.channel_layers[channel_name].visible = True
            if channel_name in self.adjustment_widgets:
                self.adjustment_widgets[channel_name].visible_checkbox.setChecked(True)
    
    def on_layer_selected(self, event):
        """Handle layer selection from napari layer list"""
        if self._updating_selection:
            return
        
        active_layer = event.value
        if active_layer is None:
            return
        
        # Get channel name, handling potential [number] suffix
        layer_name = active_layer.name
        # Extract base name if it has [number] suffix
        if ' [' in layer_name and layer_name.endswith(']'):
            channel_name = layer_name.split(' [')[0]
        else:
            channel_name = layer_name
        
        # If the layer name doesn't match our channel, check if we should use it
        # or if it's a duplicate we should remove
        if channel_name not in self.channel_files:
            # This layer doesn't belong to our channels, ignore it
            return
        
        # Load channel data if not already loaded
        if channel_name not in self.channel_normalized_cache:
            self._load_channel_data(channel_name)
        
        # Check if this layer is already in our tracking
        if channel_name in self.channel_layers:
            # We already have this channel tracked
            layer = self.channel_layers[channel_name]
            # If the selected layer is different from our tracked one, remove the duplicate
            if layer != active_layer:
                # Remove the duplicate layer
                if active_layer in self.viewer.layers:
                    self.viewer.layers.remove(active_layer)
                # Use our tracked layer
                self.viewer.layers.selection.active = layer
            else:
                # Make sure it's visible
                if not layer.visible:
                    layer.visible = True
                    if channel_name in self.adjustment_widgets:
                        self.adjustment_widgets[channel_name].visible_checkbox.setChecked(True)
                
                # Refresh the display with current adjustments
                if channel_name in self.channel_normalized_cache:
                    img = self.channel_normalized_cache[channel_name]
                    adjusted_img = self.apply_adjustments(channel_name, img)
                    layer.data = adjusted_img
        else:
            # This is a new layer, register it and update
            if layer_name != channel_name:
                # Fix the name if it has [number] suffix
                active_layer.name = channel_name
            self.channel_layers[channel_name] = active_layer
            
            # Load channel data and update
            if channel_name in self.channel_normalized_cache:
                img = self.channel_normalized_cache[channel_name]
                adjusted_img = self.apply_adjustments(channel_name, img)
                active_layer.data = adjusted_img
            
            # Make sure it's visible
            if not active_layer.visible:
                active_layer.visible = True
                if channel_name in self.adjustment_widgets:
                    self.adjustment_widgets[channel_name].visible_checkbox.setChecked(True)
        
        # Update combo box and slider to match selection
        self._updating_selection = True
        try:
            index = self.channel_combo.findText(channel_name)
            if index >= 0 and self.channel_combo.currentIndex() != index:
                self.channel_combo.setCurrentIndex(index)
            
            # Update slider if in single channel mode
            if self.single_channel_active and channel_name in self.channel_list:
                slider_idx = self.channel_list.index(channel_name)
                if self.channel_slider.value() != slider_idx:
                    self.channel_slider.setValue(slider_idx)
        finally:
            self._updating_selection = False
        
        # Scroll to the adjustment widget
        if channel_name in self.adjustment_widgets:
            widget = self.adjustment_widgets[channel_name]
            scroll_area = widget.parent().parent()
            if isinstance(scroll_area, QScrollArea):
                scroll_area.ensureWidgetVisible(widget)
    
    def eventFilter(self, obj, event):
        """Event filter to handle canvas and window resize events for adaptive sizing"""
        try:
            from qtpy.QtCore import QEvent
            
            # Check if this is a resize event
            if event.type() == QEvent.Resize:
                # Don't update during loading or if already updating
                if self._is_loading or self._updating_slider_position:
                    return False
                
                # Update slider position when canvas or window is resized
                # Use debounced update to prevent rapid-fire updates
                self._debounced_update_slider_position()
        except:
            pass
        return False  # Let the event continue to be processed
    
    def update_slider_width(self):
        """Update slider width - now uses overlay positioning"""
        # This function is kept for compatibility but now uses overlay positioning
        self._update_slider_overlay_position()
    
    def _set_window_icon(self):
        """Set the window icon for VividScope"""
        try:
            # Try to load icon from common locations
            # Priority: vividscope_icon.ico.png (program icon) first
            icon_paths = [
                Path(__file__).parent / "vividscope_icon.ico.png",  # Primary program icon
                Path(__file__).parent / "vividscope_icon.ico",
                Path(__file__).parent / "vividscope_icon.png",
                Path(__file__).parent / "icon.png",
                Path(__file__).parent / "icon.ico",
                Path(__file__).parent / "resources" / "icons" / "vividscope_icon.ico.png",
                Path(__file__).parent / "resources" / "icons" / "vividscope_icon.png",
                Path(__file__).parent / "resources" / "icons" / "vividscope_icon.ico",
            ]
            
            icon_path = None
            for path in icon_paths:
                if path.exists():
                    icon_path = path
                    break
            
            if icon_path:
                icon = QIcon(str(icon_path))
                # Set icon on the napari window - use a small delay to ensure window is ready
                QTimer.singleShot(100, lambda: self._apply_window_icon(icon))
        except Exception:
            # Silently fail if icon can't be set - not critical
            pass
    
    def _apply_window_icon(self, icon: QIcon):
        """Apply the icon to the window (called with delay to ensure window exists)"""
        try:
            if hasattr(self.viewer, 'window') and hasattr(self.viewer.window, '_qt_window'):
                self.viewer.window._qt_window.setWindowIcon(icon)
                # Also set for the application
                QApplication.instance().setWindowIcon(icon)
        except Exception:
            pass
    
    def run(self):
        """Run the viewer"""
        napari.run()


def main():
    """Main entry point"""
    viewer = VividScopeViewer()
    viewer.run()


if __name__ == "__main__":
    main()

