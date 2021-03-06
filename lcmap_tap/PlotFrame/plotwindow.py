"""Generate a matplotlib canvas and add it to a QWidget contained in a QMainWindow.  This will provide the
display and interactions for the PyCCD plots."""

import datetime as dt

import matplotlib
import numpy as np
from PyQt5 import QtWidgets, QtCore

matplotlib.use("Qt5Agg")

from matplotlib.collections import PathCollection

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar


class MplCanvas(FigureCanvas):
    """
    TODO: Add summary line
    """

    def __init__(self, fig):
        """
        TODO: Add Summary
        Args:
            fig:
        """
        self.fig = fig

        FigureCanvas.__init__(self, self.fig)

        if len(fig.axes) >= 3:
            sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Minimum)
        else:
            sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)

        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)

        FigureCanvas.setSizePolicy(self, sizePolicy)

        FigureCanvas.updateGeometry(self)


class PlotWindow(QtWidgets.QMainWindow):
    def __init__(self, fig, axes, artist_map, lines_map, gui, scenes, parent=None):
        """
        TODO Add a summary
        Args:
            fig:
            axes:
            artist_map:
            lines_map:
            gui:
            scenes:
            parent:
        """

        super(PlotWindow, self).__init__(parent)

        self.widget = QtWidgets.QWidget()
        self.setCentralWidget(self.widget)
        self.widget.setLayout(QtWidgets.QVBoxLayout())
        self.widget.layout().setContentsMargins(0, 0, 0, 0)
        self.widget.layout().setSpacing(0)

        self.fig = fig
        self.canvas = MplCanvas(fig=self.fig)
        self.canvas.draw()

        # <matplotlib.axes.Axes> All axes in the figure are linked via sharey=True, only need one axes object
        # to control zooming on all axes simultaneously.
        self.ax = axes.flatten()[0]

        # <tuple> Contains the original x-axes (i.e. date) limits in order (left, right)
        self.xlim_original = self.ax.get_xlim()

        # <dict> For containing the information pulled by the point_pick method defined below
        self.value_holder = dict()

        def point_pick(event):
            """
            Define a picker method to grab data off of the plot wherever the mouse cursor is when clicked

            Args:
                event: A mouse-click event
                       event.button == 1 <left-click>
                       event.button == 2 <wheel-click>
                       event.button == 3 <right-click>

            Returns:
                The x_data and y_data for the selected artist using a mouse click event

            """
            # Reference useful information about the pick location
            mouse_event = event.mouseevent

            # This references which object on the plot was hit by the pick
            artist = event.artist

            # Only works using left-click (event.mouseevent.button==1)
            # and on any of the scatter point series (PathCollection artists)
            if isinstance(artist, PathCollection) and mouse_event.button == 1:
                # Return the index value of the artist (i.e. which data point in the series was hit)
                ind = event.ind

                # Retrieve the appropriate data series based on the clicked artist
                x = artist_map[artist][0]
                y = artist_map[artist][1]
                b = artist_map[artist][2]

                try:
                    # Grab the date value at the clicked point
                    click_x = dt.datetime.fromordinal(int(mouse_event.xdata))

                    point_clicked = [click_x, mouse_event.ydata]

                    # Retrieve the x-y data for the plotted point within a set tolerance to the
                    # clicked point if there is one
                    nearest_x = dt.datetime.fromordinal(int(np.take(x, ind)))
                    nearest_y = np.take(y, ind)

                    artist_data = [nearest_x, nearest_y]

                    self.value_holder["temp"] = [point_clicked, artist_data]

                    test_str = "{:%Y%m%d}".format(self.value_holder["temp"][1][0])

                    print("point clicked: {}\n\
                          nearest artist: {}\n\
                          artist data: {}\n\
                          subplot: {}".format(point_clicked, self.value_holder, artist_data, b))

                    # Look through the scene IDs to find which one corresponds to the selected obs. date
                    for scene in scenes:
                        if test_str in scene:
                            self.value_holder["temp"].append(scene)

                            gui.ui.clicked_listWidget.addItem("Scene ID: {}\n"
                                                              "Obs. Date: {:%Y-%b-%d}\n"
                                                              "{}-Value: {}".format(scene,
                                                                                    self.value_holder['temp'][1][0],
                                                                                    b,
                                                                                    self.value_holder['temp'][1][1][0]))
                            break

                # I think the TypeError might occur when more than a single data point is returned with one click,
                # but need to investigate further.
                except TypeError:
                    pass

            else:
                # Do this so nothing happens when the other mouse buttons are clicked while over a plot
                return False, dict()

        def leg_pick(event):
            """
            Define a picker method that allows toggling lines on/off by clicking them on the legend
            Args:
                event: A mouse-click event

            Returns:

            """
            mouseevent = event.mouseevent

            # Only want this to work if the left mouse button is clicked (value == 1)
            if mouseevent.button == 1:

                try:
                    legline = event.artist

                    # The origlines is a list of lines mapped to the legline for that particular subplot
                    origlines = lines_map[legline]

                    for l in origlines:

                        # Reference the opposite of the line's current visibility
                        vis = not l.get_visible()

                        # Make it so
                        l.set_visible(vis)

                        # Change the transparency of the picked object in the legend so the user can see explicitly
                        # which items are turned on/off.  This doesn't work for the points in the legend currently.
                        if vis:
                            legline.set_alpha(1.0)

                        else:
                            legline.set_alpha(0.2)

                    # Redraw the canvas with the line or points turned on/off
                    self.canvas.draw()

                except KeyError:
                    return False, dict()

            else:
                return False, dict()

        def enter_axes(event):
            """
            Detect when the cursor enters a subplot area on the main canvas.  Install the overridden EventFilter
            which deactivates the mouse wheel scrolling on the QMainWindow
            Args:
                event: The 'axes_enter_event'

            Returns:
                None

            """
            if event:
                self.scroll.viewport().installEventFilter(self)

        def leave_axes(event):
            """
            Detect when the cursor leaves a subplot area on the main canvas.  Remove the overridden EventFilter
            to reactivate mouse wheel scrolling on the QMainWindow
            Args:
                event: The 'axes_leave_event'

            Returns:
                None

            """
            if event:
                self.scroll.viewport().removeEventFilter(self)

        def zoom_event(event, base_scale=2.):
            """
            Enable zooming in/out of the plots using the mouse scroll wheel.  Currently zoom on the x-axis only.
            Source: https://gist.github.com/tacaswell/3144287

            Args:
                event: <scroll-event> Signal went when the scroll wheel is used inside of a plot window
                base_scale: <float> Default is 2, the re-scaling factor.

            Returns:
                None
            """
            cur_xlim = self.ax.get_xlim()

            # <float> The x-axis value where the mouse scroll event occurs
            xdata = event.xdata

            # Decrease by scale factor (zoom in)
            if event.button == "up":
                scale_factor = 1 / base_scale

            # Increase by scale factor (zoom out)
            elif event.button == "down":
                scale_factor = base_scale

            else:
                scale_factor = 1

            try:
                # <float> X-Distance from cursor to current left-limit
                x_left_dist = xdata - cur_xlim[0]

                # <float> X-Distance from cursor to current right-limit
                x_right_dist = cur_xlim[1] - xdata

                # <float> The x-axis rescaled left-limit
                x_left = xdata - x_left_dist * scale_factor

                # <float> The x-axis rescaled right-limit
                x_right = xdata + x_right_dist * scale_factor

                if x_left >= self.xlim_original[0] and x_right <= self.xlim_original[1]:

                    self.ax.set_xlim([x_left, x_right])

                elif x_left >= self.xlim_original[0] and x_right > self.xlim_original[1]:

                    self.ax.set_xlim([x_left, self.xlim_original[1]])

                elif x_left < self.xlim_original[0] and x_right <= self.xlim_original[1]:

                    self.ax.set_xlim([self.xlim_original[0], x_right])

                else:

                    pass

                self.canvas.draw()

            # occurs using the scroll button outside of an axis, but still in the plot window
            except TypeError:
                pass

        self.nav = NavigationToolbar(self.canvas, self.widget)

        self.widget.layout().addWidget(self.nav)

        self.widget.layout().addWidget(self.canvas)

        self.scroll = QtWidgets.QScrollArea(self.widget)

        self.scroll.setWidgetResizable(True)

        self.scroll.setWidget(self.canvas)

        self.widget.layout().addWidget(self.scroll)

        self.canvas.mpl_connect("pick_event", point_pick)

        self.canvas.mpl_connect("pick_event", leg_pick)

        self.canvas.mpl_connect("axes_enter_event", enter_axes)

        self.canvas.mpl_connect("axes_leave_event", leave_axes)

        self.canvas.mpl_connect("scroll_event", zoom_event)

        self.show()

    def eventFilter(self, source, event):
        """
        Override the parent class eventFilter method to ignore the mouse scroll wheel when zooming in a plot

        Args:
            source:
            event:

        Returns:

        """
        if event.type() == QtCore.QEvent.Wheel and source is self.scroll.viewport():
            return True

        return super(PlotWindow, self).eventFilter(source, event)
