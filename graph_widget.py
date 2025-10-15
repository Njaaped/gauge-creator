# graph_widget.py
# This module contains a custom PyQtGraph widget for displaying
# cycling data and handling interactive range selection.

import pyqtgraph as pg
from pyqtgraph import DateAxisItem
from PyQt6.QtCore import pyqtSignal

class GraphWidget(pg.PlotWidget):
    """
    A custom plot widget that displays power over time. The user can
    zoom and pan with the mouse, and the visible range is emitted.
    """
    # Signal to emit the selected region's start and end timestamps
    regionChanged = pyqtSignal(int, int)

    def __init__(self, *args, **kwargs):
        super().__init__(axisItems={'bottom': DateAxisItem()}, *args, **kwargs)

        self.setLabel('left', 'Power (W)')
        self.setLabel('bottom', 'Time')
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setBackground('w') # White background for better visibility
        self.getPlotItem().getViewBox().setMouseMode(pg.ViewBox.RectMode) # Ensure right-click drag is zoom

        # The line that will display the power data
        self.power_curve = self.plot(pen=pg.mkPen('b', width=2)) # Blue pen, width 2

        # When the user zooms or pans, the sigXRangeChanged signal is emitted.
        # We connect that to our internal handler.
        self.getPlotItem().getViewBox().sigXRangeChanged.connect(self._on_view_changed)

    def plot_data(self, trackpoints):
        """
        Updates the plot with new trackpoint data.

        Args:
            trackpoints (list): A list of trackpoint dictionaries from the backend.
        """
        if not trackpoints:
            self.power_curve.clear()
            return

        # Convert datetime objects to Unix timestamps for plotting
        times = [tp['time'].timestamp() for tp in trackpoints]
        power = [tp['power'] for tp in trackpoints]

        self.power_curve.setData(x=times, y=power)
        # The view will auto-range, triggering _on_view_changed automatically

    def _on_view_changed(self):
        """
        Internal handler that fires when the user zooms or pans.
        It gets the visible X-axis range and emits the public regionChanged signal.
        """
        # .viewRange() returns a list of two lists: [[xmin, xmax], [ymin, ymax]]
        visible_x_range = self.getPlotItem().getViewBox().viewRange()[0]
        min_x, max_x = visible_x_range
        self.regionChanged.emit(int(min_x), int(max_x))