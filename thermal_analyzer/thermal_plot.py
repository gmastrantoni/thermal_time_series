import numpy as np
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Polygon
from matplotlib.path import Path
import tkinter as tk
from tkinter import ttk
from utils.config import config
import matplotlib.colors as mcolors
import os
import webbrowser
from plotly.offline import plot
from plotly.io import to_html


class ThermalPlotter:
    def __init__(self, plot_frame):
        self.plot_frame = plot_frame
        self.fig_thermal = None
        self.ax_thermal = None
        self.canvas_thermal = None
        self.fig_timeseries = None
        self.ax_timeseries = None
        self.canvas_timeseries = None
        self.polygon_patch = None
        
        # Store multiple points with their colors
        self.points = []  # List of (x, y, color) tuples
        self.point_markers = []  # Store plot markers for easy removal
        
        # Generate a color cycle for points
        self.colors = list(mcolors.TABLEAU_COLORS.values())
        self.current_color_idx = 0
        
        # Store time series data for CSV export
        self.current_timeseries_data = {
            'timestamps': None,
            'values': {},  # Dictionary mapping point index to values
            'mins': None,
            'maxs': None,
            'selection_type': None
        }

        # Create temp directory for plot files if it doesn't exist
        self.temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        
        self.setup_plots()

    def setup_plots(self):
        """Initialize matplotlib figures and canvases"""
        # Thermal image plot
        self.fig_thermal = Figure(figsize=(10, 8), constrained_layout=True)
        self.ax_thermal = self.fig_thermal.add_subplot(111)
        self.canvas_thermal = FigureCanvasTkAgg(self.fig_thermal, master=self.plot_frame)
        self.canvas_thermal.draw()
        canvas_widget = self.canvas_thermal.get_tk_widget()
        canvas_widget.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        
        # Time series plot (using regular matplotlib for consistency)
        self.fig_timeseries = Figure(figsize=(10, 4), constrained_layout=True)
        self.ax_timeseries = self.fig_timeseries.add_subplot(111)
        self.canvas_timeseries = FigureCanvasTkAgg(self.fig_timeseries, master=self.plot_frame)
        self.canvas_timeseries.draw()
        self.canvas_timeseries.get_tk_widget().grid(row=1, column=0, padx=5, pady=5, sticky='nsew')
        
        # Configure grid weights
        self.plot_frame.grid_columnconfigure(0, weight=1)
        self.plot_frame.grid_rowconfigure(0, weight=2)
        self.plot_frame.grid_rowconfigure(1, weight=1)
        
        # Set initial axes positions that will be maintained
        self.ax_thermal.set_position([0.1, 0.1, 0.75, 0.85])  # [left, bottom, width, height]

    def plot_thermal_image(self, data, timestamp=None, vmin=None, vmax=None):
        """Plot thermal image with optional timestamp and fixed colorbar range"""
        self.ax_thermal.clear()
        
        # Maintain consistent axes position
        self.ax_thermal.set_position([0.1, 0.1, 0.75, 0.85])
        
        # Remove old colorbar if it exists
        if len(self.fig_thermal.axes) > 1:
            self.fig_thermal.delaxes(self.fig_thermal.axes[1])
        
        # Plot image with fixed aspect ratio and colorbar range
        im = self.ax_thermal.imshow(data, cmap=config.COLORMAP, aspect='equal', 
                        interpolation='nearest', vmin=vmin, vmax=vmax)
        
        # Add colorbar with consistent size
        cbar = self.fig_thermal.colorbar(im, ax=self.ax_thermal, 
                                    label='Temperature (°C)',
                                    pad=0.02)
        
        # Create title with timestamp and colorbar range if available
        title = 'Thermal Image'
        if timestamp:
            title = f'{title} - {timestamp.strftime("%Y-%m-%d %H:%M:%S")}'
        # if vmin is not None and vmax is not None:
        #     title = f'{title}\nColorbar Range: {vmin:.2f}°C to {vmax:.2f}°C'
        
        self.ax_thermal.set_title(title, pad=10)
        
        self.canvas_thermal.draw()

    def get_next_color(self):
        """Get the next color from the color cycle"""
        color = self.colors[self.current_color_idx]
        self.current_color_idx = (self.current_color_idx + 1) % len(self.colors)
        return color

    def plot_point(self, x, y):
        """Plot a new point with simplified numbering"""
        color = self.get_next_color()
        self.points.append((x, y, color))
        
        # Plot point with simple number label
        point_num = len(self.points)
        # Add the point marker with a plus sign
        marker = self.ax_thermal.plot(x, y, '+', color=color, markersize=10, linewidth=2)[0]
        # Add the point number label
        text = self.ax_thermal.text(x + 1, y + 1, str(point_num), color=color, 
                                  fontweight='bold', bbox=dict(facecolor='white', alpha=0.7))
        
        self.point_markers.extend([marker, text])
        self.canvas_thermal.draw()
        return point_num - 1

    def plot_line(self, x1, y1, x2, y2):
        """Plot a line between two points and track it for proper removal"""
        line = self.ax_thermal.plot([x1, x2], [y1, y2], 'w--')[0]
        # Add the line to the point_markers list for proper removal later
        self.point_markers.append(line)
        self.canvas_thermal.draw()

    def plot_polygon(self, coords):
        """Plot the completed polygon and ensure it can be properly cleared"""
        # Remove existing polygon if present
        if self.polygon_patch:
            self.polygon_patch.remove()
        
        # Create new polygon with white outline
        self.polygon_patch = Polygon(coords, fill=False, color='white', linewidth=2, linestyle='dashed')
        self.ax_thermal.add_patch(self.polygon_patch)
        
        # Complete the polygon by connecting last point to first point
        if len(coords) > 2:
            first_x, first_y = coords[0]
            last_x, last_y = coords[-1]
            closing_line = self.ax_thermal.plot([last_x, first_x], [last_y, first_y], 'w--')[0]
            self.point_markers.append(closing_line)
        
        self.canvas_thermal.draw()

    def plot_time_series(self, timestamps, values_dict=None, mins=None, maxs=None):
        """Plot time series data with simplified labels in legend"""
        self.ax_timeseries.clear()
        
        if self.current_timeseries_data['selection_type'] == 'point':
            # Plot multiple point time series with simple point numbering
            for point_idx, values in values_dict.items():
                _, _, color = self.points[point_idx]
                label = f'Point {point_idx + 1}'  # Simplified label
                self.ax_timeseries.plot(timestamps, values, 'o:', markersize=5, color=color, label=label, alpha=.85, markeredgecolor='k')
        else:
            # Polygon statistics time series (unchanged)
            self.ax_timeseries.plot(timestamps, values_dict['mean'], 'go:', label='Mean', alpha=1, markeredgecolor='k')
            self.ax_timeseries.plot(timestamps, mins, 'bo:', label='Min', alpha=.85, markeredgecolor='k')
            self.ax_timeseries.plot(timestamps, maxs, 'ro:', label='Max', alpha=.85, markeredgecolor='k')
        
        self.fig_timeseries.autofmt_xdate()
        
        self.ax_timeseries.set_xlabel('Time')
        self.ax_timeseries.set_ylabel('Temperature (°C)')
        self.ax_timeseries.set_title('Temperature Time Series')
        self.ax_timeseries.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        self.ax_timeseries.grid(True)
        
        # Adjust layout to prevent legend cutoff
        self.fig_timeseries.tight_layout()

        # Create the interactive plot HTML file
        self.create_interactive_plot(timestamps, values_dict, mins, maxs)
        
        self.canvas_timeseries.draw()
    
    def create_interactive_plot(self, timestamps, values_dict, mins=None, maxs=None):
        """Create the interactive Plotly plot and save to an HTML file"""
        # Create a Plotly figure
        fig = go.Figure()
        
        # Format timestamps for display
        formatted_dates = [ts.strftime('%Y-%m-%d %H:%M:%S') for ts in timestamps]
        
        # Add traces based on selection type
        if self.current_timeseries_data['selection_type'] == 'point':
            # Plot multiple point time series with simple point numbering
            for point_idx, values in values_dict.items():
                _, _, color = self.points[point_idx]
                label = f'Point {point_idx + 1}'  # Simplified label
                
                fig.add_trace(go.Scatter(
                    x=formatted_dates,
                    y=values,
                    mode='lines+markers',
                    name=label,
                    line=dict(color=color),
                    marker=dict(size=8, line=dict(width=1, color='black')),
                    hovertemplate='<b>%{fullData.name}</b><br>Time: %{x}<br>Temperature: %{y:.2f}°C<extra></extra>'
                ))
                
        else:
            # Polygon statistics time series
            fig.add_trace(go.Scatter(
                x=formatted_dates,
                y=values_dict['mean'],
                mode='lines+markers',
                name='Mean',
                line=dict(color='green'),
                marker=dict(size=8, line=dict(width=1, color='black')),
                hovertemplate='<b>Mean</b><br>Time: %{x}<br>Temperature: %{y:.2f}°C<extra></extra>'
            ))
            
            fig.add_trace(go.Scatter(
                x=formatted_dates,
                y=mins,
                mode='lines+markers',
                name='Min',
                line=dict(color='blue'),
                marker=dict(size=8, line=dict(width=1, color='black')),
                hovertemplate='<b>Min</b><br>Time: %{x}<br>Temperature: %{y:.2f}°C<extra></extra>'
            ))
            
            fig.add_trace(go.Scatter(
                x=formatted_dates,
                y=maxs,
                mode='lines+markers',
                name='Max',
                line=dict(color='red'),
                marker=dict(size=8, line=dict(width=1, color='black')),
                hovertemplate='<b>Max</b><br>Time: %{x}<br>Temperature: %{y:.2f}°C<extra></extra>'
            ))
        
        # Update layout for better appearance
        fig.update_layout(
            title='Interactive Temperature Time Series',
            xaxis_title='Time',
            yaxis_title='Temperature (°C)',
            hovermode='closest',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=20, r=20, t=40, b=20),
            plot_bgcolor='white',
            xaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                showline=True,
                linecolor='black',
                linewidth=1
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                showline=True,
                linecolor='black',
                linewidth=1
            )
        )
        
        # Save the plot to a temporary HTML file
        self.temp_html_path = os.path.join(self.temp_dir, "temp_plot.html")
        with open(self.temp_html_path, "w") as f:
            f.write(to_html(fig, include_plotlyjs='cdn', full_html=True))
    
    def open_interactive_plot(self):
        """Open the interactive plot in the default web browser"""
        if hasattr(self, 'temp_html_path') and os.path.exists(self.temp_html_path):
            webbrowser.open('file://' + os.path.abspath(self.temp_html_path))
    
    # --------------------------------------
    
    def clear_selection(self):
        """
        Clear all points and polygons completely from the thermal image.
        This ensures all visual elements are properly removed.
        """
        # Clear all line and point markers
        for marker in self.point_markers:
            marker.remove()
        self.point_markers = []
        self.points = []
        self.current_color_idx = 0
        
        # Properly remove the polygon patch
        if self.polygon_patch:
            self.polygon_patch.remove()
            self.polygon_patch = None
        
        # Clear any additional lines that might be part of the polygon
        # This is important because some lines might not be in point_markers
        for line in self.ax_thermal.lines:
            line.remove()
        
        # Reset data storage
        self.current_timeseries_data = {
            'timestamps': None,
            'values': {},
            'mins': None,
            'maxs': None,
            'selection_type': None
        }
        
        # Redraw the canvas to ensure all elements are properly cleared
        self.canvas_thermal.draw()
        
        # Clear time series plot
        self.ax_timeseries.clear()
        self.canvas_timeseries.draw()

    def clear_polygon(self):
        """Clear polygon and point markers"""
        if self.polygon_patch:
            self.polygon_patch.remove()
            self.polygon_patch = None
        
        # Clear any point markers
        for artist in self.ax_thermal.lines:
            artist.remove()
        
        self.canvas_thermal.draw()
        self.ax_timeseries.clear()
        self.canvas_timeseries.draw()
        
    def clear_workspace(self):
        """Clear all plots and reset to initial state"""
        # Clear thermal image plot
        self.ax_thermal.clear()
        if self.polygon_patch:
            self.polygon_patch.remove()
            self.polygon_patch = None
        
        # Maintain consistent axes position and appearance
        self.ax_thermal.set_position([0.1, 0.1, 0.75, 0.85])
        self.ax_thermal.set_title('Thermal Image')
        
        # Set initial axis limits
        self.ax_thermal.set_xlim(0, 336)  # Based on your image dimensions
        self.ax_thermal.set_ylim(252, 0)  # Inverted for image coordinates
        
        # Remove colorbar if it exists
        if len(self.fig_thermal.axes) > 1:
            self.fig_thermal.delaxes(self.fig_thermal.axes[1])
        
        # Clear time series plot
        self.ax_timeseries.clear()
        self.ax_timeseries.set_title('Temperature Statistics')
        self.ax_timeseries.set_xlabel('Time')
        self.ax_timeseries.set_ylabel('Temperature (°C)')
        self.ax_timeseries.grid(True)
        self.ax_timeseries.set_xlim(0, 1)
        self.ax_timeseries.set_ylim(0, 1)
        
        # Redraw both canvases
        self.canvas_thermal.draw()
        self.canvas_timeseries.draw()

    def create_polygon_mask(self, data_shape, polygon_coords):
        """Create boolean mask from polygon coordinates"""
        mask = np.zeros(data_shape, dtype=bool)
        
        # Convert polygon coordinates to integer indices
        polygon_coords_int = np.array(polygon_coords).astype(int)
        
        # Create vertex list for path
        path = Path(polygon_coords_int)
        
        # Create grid of points
        x, y = np.meshgrid(np.arange(data_shape[1]), np.arange(data_shape[0]))
        points = np.vstack((x.flatten(), y.flatten())).T
        
        # Test which points are inside the polygon
        mask = path.contains_points(points).reshape(data_shape)
        
        return mask

    def save_plots(self, base_filename):
        """Save both thermal and time series plots, and time series data as CSV"""
        # Save thermal image plot
        thermal_filename = f"{base_filename}_thermal.png"
        self.fig_thermal.savefig(thermal_filename, bbox_inches='tight', dpi=300)
        
        # Save time series plot
        timeseries_filename = f"{base_filename}_timeseries.png"
        self.fig_timeseries.savefig(timeseries_filename, bbox_inches='tight', dpi=300)

        # Also save an interactive HTML version if we have time series data
        html_filename = None
        if self.current_timeseries_data['timestamps'] is not None:
            html_filename = f"{base_filename}_interactive_timeseries.html"
            
            # Create a new Plotly figure for saving
            fig = go.Figure()
            
            formatted_dates = [ts.strftime('%Y-%m-%d %H:%M:%S') 
                              for ts in self.current_timeseries_data['timestamps']]
            
            if self.current_timeseries_data['selection_type'] == 'point':
                for point_idx, values in self.current_timeseries_data['values'].items():
                    if point_idx < len(self.points):  # Make sure the point exists
                        _, _, color = self.points[point_idx]
                        label = f'Point {point_idx + 1}'
                        
                        fig.add_trace(go.Scatter(
                            x=formatted_dates,
                            y=values,
                            mode='lines+markers',
                            name=label,
                            line=dict(color=color),
                            marker=dict(size=8, line=dict(width=1, color='black'))
                        ))
            else:
                fig.add_trace(go.Scatter(
                    x=formatted_dates,
                    y=self.current_timeseries_data['values']['mean'],
                    mode='lines+markers',
                    name='Mean',
                    line=dict(color='green'),
                    marker=dict(size=8, line=dict(width=1, color='black'))
                ))
                
                fig.add_trace(go.Scatter(
                    x=formatted_dates,
                    y=self.current_timeseries_data['mins'],
                    mode='lines+markers',
                    name='Min',
                    line=dict(color='blue'),
                    marker=dict(size=8, line=dict(width=1, color='black'))
                ))
                
                fig.add_trace(go.Scatter(
                    x=formatted_dates,
                    y=self.current_timeseries_data['maxs'],
                    mode='lines+markers',
                    name='Max',
                    line=dict(color='red'),
                    marker=dict(size=8, line=dict(width=1, color='black'))
                ))
            
            # Update layout
            fig.update_layout(
                title='Interactive Temperature Time Series',
                xaxis_title='Time',
                yaxis_title='Temperature (°C)',
                hovermode='closest',
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Save the interactive HTML file
            with open(html_filename, 'w') as f:
                f.write(to_html(fig, include_plotlyjs='cdn', full_html=True))

        # Save time series data as CSV if available
        csv_filename = None
        if self.current_timeseries_data['timestamps'] is not None:
            csv_filename = f"{base_filename}_timeseries.csv"
            self._export_timeseries_data(csv_filename)
        
        return thermal_filename, timeseries_filename, csv_filename
    

    
    def _export_timeseries_data(self, filename):
        """Export time series data to CSV with simplified column names"""
        if self.current_timeseries_data['timestamps'] is None:
            return
            
        # Create a dictionary with timestamps
        data_dict = {
            'Timestamp': [ts.strftime('%Y-%m-%d %H:%M:%S') 
                         for ts in self.current_timeseries_data['timestamps']]
        }
        
        if self.current_timeseries_data['selection_type'] == 'point':
            # Add data for each point with simple numbering
            for point_idx, values in self.current_timeseries_data['values'].items():
                column_name = f'Point_{point_idx + 1}'  # Simplified column name
                data_dict[column_name] = values
        else:
            # Polygon statistics (unchanged)
            data_dict.update({
                'Mean_Temperature': self.current_timeseries_data['values']['mean'],
                'Min_Temperature': self.current_timeseries_data['mins'],
                'Max_Temperature': self.current_timeseries_data['maxs']
            })
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(data_dict)
        
        # Format floating point numbers
        for col in df.select_dtypes(include=['float64']).columns:
            df[col] = df[col].round(3)
            
        df.to_csv(filename, index=False)


    def get_click_handler(self):
        """Return the canvas for click event binding"""
        return self.canvas_thermal
    

class DeltaAnalysisWindow:
    """Window for displaying thermal time series delta analysis."""
    def __init__(self, parent, timestamps, values_dict, window_size, selection_type):
        """
        Initialize delta analysis window.
        
        Parameters:
        -----------
        parent : tk.Tk
            Parent window
        timestamps : list
            List of datetime objects
        values_dict : dict
            Dictionary mapping point indices (or 'mean') to temperature lists
        window_size : int
            Window size for computing delta (e.g., 2 means delta from 2 timestamps ago)
        selection_type : str
            'point' or 'polygon'
        """
        self.window = tk.Toplevel(parent)
        self.window.title(f"Delta Analysis (Window Size: {window_size})")
        self.window.geometry("800x400")
        self.window.minsize(500, 250)
        
        # Configure the window to expand properly
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(0, weight=1)
        
        # Create matplotlib figure and canvas
        self.fig = Figure(figsize=(8, 6), constrained_layout=True)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.window)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        
        # Compute and plot delta values
        self.plot_delta_analysis(timestamps, values_dict, window_size, selection_type)
        
        # Add a close button
        close_button = ttk.Button(self.window, text="Close", command=self.window.destroy)
        close_button.grid(row=1, column=0, pady=10)
    
    def plot_delta_analysis(self, timestamps, values_dict, window_size, selection_type):
        """
        Compute and plot delta values.
        
        Delta is calculated as current value minus the value 'window_size' steps ago.
        """
        if len(timestamps) <= window_size:
            self.ax.text(0.5, 0.5, 
                    f"Not enough data points for window size {window_size}.\n"
                    f"Need at least {window_size+1} data points.",
                    ha='center', va='center', transform=self.ax.transAxes,
                    fontsize=12)
            self.canvas.draw()
            return
        
        # Create copies of lists for delta calculation
        delta_timestamps = timestamps[window_size:]
        
        # Calculate delta values for each point or polygon stats
        if selection_type == 'point':
            # For point selection
            delta_values = {}
            for point_idx, values in values_dict.items():
                delta = [values[i] - values[i-window_size] for i in range(window_size, len(values))]
                delta_values[point_idx] = delta
                
                # Plot with the same color scheme as original
                label = f'Point {point_idx + 1}'
                self.ax.plot(delta_timestamps, delta, 'd:', label=label, alpha=.85, markeredgecolor='k')
                
        else:
            # For polygon selection
            mean_values = values_dict['mean']
            delta_mean = [mean_values[i] - mean_values[i-window_size] 
                        for i in range(window_size, len(mean_values))]
            
            # Plot mean delta
            self.ax.plot(delta_timestamps, delta_mean, 'bd:', label='Mean Δ', alpha=.85, markeredgecolor='k')
        
        # Format the plot
        self.fig.autofmt_xdate()
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('Temperature Change (°C)')
        self.ax.set_title(f'Temperature Delta (Window Size: {window_size})')
        self.ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        self.ax.grid(True)
        
        # Add zero reference line
        self.ax.axhline(y=0, color='r', linestyle='-', alpha=0.3)
        
        # Adjust layout
        self.fig.tight_layout()
        self.canvas.draw()