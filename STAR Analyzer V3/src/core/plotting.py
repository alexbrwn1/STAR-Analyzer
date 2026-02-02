"""
Raster plot generation for operant behavioral data.
Creates visualizations of lever presses, licks, and sipper events.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import numpy as np

from .data_models import PassStatus


# Color scheme - bold, saturated colors
COLORS = {
    'active_press': '#00aa00',       # Bold green
    'inactive_press': '#dd0000',     # Bold red
    'lick': '#000000',               # Black
    'sipper_region': '#add8e6',      # Light blue for sipper periods
    'sipper_edge': '#4a90d9',        # Darker blue for edges
    'lick_criterion': '#00cccc',     # Cyan for 100-lick criterion line
    'background': '#ffffff',         # White
    'axis': '#333333',               # Dark gray for axis
}


# Pass status badge colors: (background, text, edge)
PASS_BADGE_COLORS = {
    PassStatus.PASS: ("#90EE90", "#228B22", "#228B22"),
    PassStatus.PARTIAL: ("#FFFF99", "#B8860B", "#B8860B"),
    PassStatus.FAIL: ("#FFB6C1", "#DC143C", "#DC143C"),
}


def _add_pass_status_badge(ax: plt.Axes, passed: bool, pass_status: str) -> None:
    """Draw a coloured pass/fail badge in the top-right corner of *ax*."""
    colors = PASS_BADGE_COLORS.get(pass_status, PASS_BADGE_COLORS[PassStatus.FAIL])
    bg, fg, edge = colors
    label = "Yes" if passed else "No"
    ax.text(
        0.99, 0.92, label,
        transform=ax.transAxes,
        ha="right", va="top",
        fontsize=9, fontweight="bold", color=fg,
        bbox=dict(
            boxstyle="round,pad=0.3",
            facecolor=bg,
            edgecolor=edge,
            linewidth=1.2,
        ),
        zorder=20,
    )


def create_raster_plot(data: Dict[str, Any], ax: Optional[plt.Axes] = None,
                       figsize: tuple = (12, 3)) -> tuple:
    """
    Generate a raster plot for a single session.

    Args:
        data: Parsed session data dictionary
        ax: Optional existing axes to plot on
        figsize: Figure size (width, height) in inches

    Returns:
        Tuple of (figure, axes)
    """
    # Create figure if not provided
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize, facecolor=COLORS['background'])
    else:
        fig = ax.get_figure()

    ax.set_facecolor(COLORS['background'])

    # Extract data arrays
    arrays = data.get('arrays', {})
    scalars = data.get('scalars', {})
    protocol = data.get('protocol', {})

    # Get timestamp arrays (using defaults if not present)
    # J = active lever presses, K = inactive lever presses
    # L = sipper activations, N = licks, O = other events
    active_presses = arrays.get('J', [])
    inactive_presses = arrays.get('K', [])
    sipper_times = arrays.get('L', [])
    licks = arrays.get('N', [])

    # Get session duration
    session_duration = scalars.get('T', 0)
    if session_duration == 0 and any([active_presses, inactive_presses, licks]):
        # Estimate from data
        all_times = active_presses + inactive_presses + licks + sipper_times
        if all_times:
            session_duration = max(all_times) * 1.1

    # Get sipper duration from protocol (default to 10 seconds)
    sipper_duration = protocol.get('sipper_duration', 10) or 10

    # Add sipper periods first (background layer)
    _add_sipper_periods(ax, sipper_times, sipper_duration)

    # Plot active presses (green lines)
    if active_presses:
        ax.eventplot([active_presses], lineoffsets=0, linelengths=0.8,
                     linewidths=1.5, colors=COLORS['active_press'],
                     orientation='horizontal')

    # Plot inactive presses (red lines)
    if inactive_presses:
        ax.eventplot([inactive_presses], lineoffsets=0, linelengths=0.8,
                     linewidths=1.0, colors=COLORS['inactive_press'],
                     orientation='horizontal')

    # Plot licks as black lines
    if licks:
        ax.eventplot([licks], lineoffsets=0, linelengths=0.8,
                     linewidths=1.0, colors=COLORS['lick'],
                     orientation='horizontal', zorder=5)

    # Add 100-lick criterion line
    _add_lick_criterion_line(ax, licks)

    # Configure axes - tight to line heights
    ax.set_xlim(0, session_duration if session_duration > 0 else 3600)
    ax.set_ylim(-0.5, 0.5)

    # Minimal styling
    ax.set_xlabel('Time (seconds)', fontsize=10, color=COLORS['axis'])
    ax.set_ylabel('')
    ax.set_yticks([])

    # Clean up spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color(COLORS['axis'])
    ax.spines['bottom'].set_linewidth(0.5)

    # Minimal gridlines
    ax.grid(True, axis='x', linestyle=':', alpha=0.3, color=COLORS['axis'])

    # Tick styling
    ax.tick_params(axis='x', colors=COLORS['axis'], labelsize=9)

    # Add title with session info
    header = data.get('header', {})
    title = _create_title(header, protocol)
    if title:
        ax.set_title(title, fontsize=11, color=COLORS['axis'], pad=10)

    plt.tight_layout()

    return fig, ax


def create_raster_plot_enhanced(data: Dict[str, Any], ax: Optional[plt.Axes] = None,
                                 figsize: tuple = (12, 4)) -> tuple:
    """
    Generate an enhanced raster plot with separate rows for different event types.

    Args:
        data: Parsed session data dictionary
        ax: Optional existing axes to plot on
        figsize: Figure size (width, height) in inches

    Returns:
        Tuple of (figure, axes)
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize, facecolor=COLORS['background'])
    else:
        fig = ax.get_figure()

    ax.set_facecolor(COLORS['background'])

    # Extract data
    arrays = data.get('arrays', {})
    scalars = data.get('scalars', {})
    protocol = data.get('protocol', {})

    active_presses = arrays.get('J', [])
    inactive_presses = arrays.get('K', [])
    sipper_times = arrays.get('L', [])
    licks = arrays.get('N', [])

    session_duration = scalars.get('T', 0)
    if session_duration == 0:
        all_times = active_presses + inactive_presses + licks + sipper_times
        if all_times:
            session_duration = max(all_times) * 1.1

    sipper_duration = protocol.get('sipper_duration', 10) or 10

    # Define row positions
    y_active = 0.6
    y_inactive = 0.2
    y_licks = -0.2
    y_sipper = -0.6

    # Add sipper periods
    for t in sipper_times:
        rect = mpatches.Rectangle((t, y_sipper - 0.15), sipper_duration, 0.3,
                                    facecolor=COLORS['sipper_region'],
                                    edgecolor=COLORS['sipper_edge'],
                                    linewidth=0.5, zorder=1)
        ax.add_patch(rect)

    # Plot active presses
    if active_presses:
        ax.eventplot([active_presses], lineoffsets=y_active, linelengths=0.25,
                     linewidths=1.5, colors=COLORS['active_press'])

    # Plot inactive presses
    if inactive_presses:
        ax.eventplot([inactive_presses], lineoffsets=y_inactive, linelengths=0.25,
                     linewidths=1.0, colors=COLORS['inactive_press'])

    # Plot licks
    if licks:
        ax.scatter(licks, [y_licks] * len(licks), s=8, c=COLORS['lick'],
                   marker='|', zorder=5, alpha=0.9)

    # Add 100-lick criterion line
    _add_lick_criterion_line(ax, licks)

    # Configure axes
    ax.set_xlim(0, session_duration if session_duration > 0 else 3600)
    ax.set_ylim(-1, 1)

    # Labels
    ax.set_xlabel('Time (seconds)', fontsize=10, color=COLORS['axis'])
    ax.set_yticks([y_active, y_inactive, y_licks, y_sipper])
    ax.set_yticklabels(['Active', 'Inactive', 'Licks', 'Sipper'], fontsize=9)

    # Clean styling
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(0.5)
    ax.spines['bottom'].set_linewidth(0.5)

    ax.grid(True, axis='x', linestyle=':', alpha=0.3)

    # Title
    header = data.get('header', {})
    title = _create_title(header, protocol)
    if title:
        ax.set_title(title, fontsize=11, pad=10)

    plt.tight_layout()

    return fig, ax


def save_raster_plot(data: Dict[str, Any], filepath: Union[str, Path],
                     enhanced: bool = False, dpi: int = 150) -> None:
    """
    Save a raster plot to file.

    Args:
        data: Parsed session data dictionary
        filepath: Output file path (supports .png, .pdf, .svg)
        enhanced: If True, use enhanced multi-row layout
        dpi: Resolution for raster formats
    """
    filepath = Path(filepath)

    if enhanced:
        fig, ax = create_raster_plot_enhanced(data)
    else:
        fig, ax = create_raster_plot(data)

    fig.savefig(filepath, dpi=dpi, bbox_inches='tight',
                facecolor=COLORS['background'], edgecolor='none')
    plt.close(fig)


def _add_sipper_periods(ax: plt.Axes, sipper_times: List[float],
                        duration: float) -> None:
    """
    Add shaded rectangles for sipper access periods.

    Args:
        ax: Matplotlib axes
        sipper_times: List of sipper activation timestamps
        duration: Duration of each sipper period in seconds
    """
    for t in sipper_times:
        rect = mpatches.Rectangle((t, -0.5), duration, 1.0,
                                    facecolor=COLORS['sipper_region'],
                                    edgecolor=COLORS['sipper_edge'],
                                    linewidth=0.5, alpha=0.5, zorder=0)
        ax.add_patch(rect)


def _create_title(header: Dict[str, Any], protocol: Dict[str, Any]) -> str:
    """Create a title string from header and protocol info."""
    parts = []

    subject = header.get('subject')
    if subject:
        parts.append(f"Subject {subject}")

    # Include experiment field (contains schedule + day info)
    experiment = header.get('experiment')
    if experiment:
        parts.append(experiment)

    # Include MSN (program name)
    msn = header.get('msn')
    if msn:
        parts.append(f"[{msn}]")

    return '  |  '.join(parts) if parts else ''


def _get_lick_criterion_time(licks: List[float], criterion: int = 100) -> Optional[float]:
    """
    Get the timestamp when the lick criterion was reached.

    Args:
        licks: List of lick timestamps (should be sorted)
        criterion: Number of licks required (default 100)

    Returns:
        Timestamp of the criterion-th lick, or None if not reached
    """
    if len(licks) >= criterion:
        sorted_licks = sorted(licks)
        return sorted_licks[criterion - 1]
    return None


def _add_lick_criterion_line(ax: plt.Axes, licks: List[float], criterion: int = 100) -> None:
    """
    Add a vertical line at the timestamp when lick criterion was reached.

    Args:
        ax: Matplotlib axes
        licks: List of lick timestamps
        criterion: Number of licks required (default 100)
    """
    criterion_time = _get_lick_criterion_time(licks, criterion)
    if criterion_time is not None:
        ax.axvline(x=criterion_time, color=COLORS['lick_criterion'],
                   linewidth=2, linestyle='-', zorder=10, alpha=0.8,
                   label=f'{criterion} licks')


def create_legend(ax: plt.Axes) -> None:
    """Add a legend to the plot."""
    legend_elements = [
        mpatches.Patch(facecolor=COLORS['active_press'], label='Active Press'),
        mpatches.Patch(facecolor=COLORS['inactive_press'], label='Inactive Press'),
        mpatches.Patch(facecolor=COLORS['lick'], label='Lick'),
        mpatches.Patch(facecolor=COLORS['sipper_region'],
                       edgecolor=COLORS['sipper_edge'], label='Sipper Access'),
        Line2D([0], [0], color=COLORS['lick_criterion'], linewidth=2, label='100 Licks'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=8,
              framealpha=0.9)


def create_multi_raster_plot(data_list: List[Dict[str, Any]],
                              figsize_per_row: tuple = (12, 1.2),
                              pass_statuses: Optional[List[Dict[str, Any]]] = None,
                              ) -> tuple:
    """
    Generate multiple raster plots stacked vertically.

    Args:
        data_list: List of parsed session data dictionaries
        figsize_per_row: Figure size (width, height) per row in inches
        pass_statuses: Optional list of dicts with 'passed' (bool) and
            'pass_status' (str) keys, one per session. When provided a
            coloured badge is drawn in the top-right of each subplot.

    Returns:
        Tuple of (figure, list of axes)
    """
    n_sessions = len(data_list)
    if n_sessions == 0:
        fig, ax = plt.subplots(figsize=figsize_per_row)
        ax.text(0.5, 0.5, 'No data loaded', ha='center', va='center', fontsize=12)
        ax.set_xticks([])
        ax.set_yticks([])
        return fig, [ax]

    # Calculate total figure height
    fig_width = figsize_per_row[0]
    fig_height = figsize_per_row[1] * n_sessions

    # Create subplots
    fig, axes = plt.subplots(n_sessions, 1, figsize=(fig_width, fig_height),
                              facecolor=COLORS['background'], squeeze=False)
    axes = axes.flatten()

    for i, (data, ax) in enumerate(zip(data_list, axes)):
        ax.set_facecolor(COLORS['background'])

        # Extract data arrays
        arrays = data.get('arrays', {})
        scalars = data.get('scalars', {})
        protocol = data.get('protocol', {})

        active_presses = arrays.get('J', [])
        inactive_presses = arrays.get('K', [])
        sipper_times = arrays.get('L', [])
        licks = arrays.get('N', [])

        # Get session duration
        session_duration = scalars.get('T', 0)
        if session_duration == 0 and any([active_presses, inactive_presses, licks]):
            all_times = active_presses + inactive_presses + licks + sipper_times
            if all_times:
                session_duration = max(all_times) * 1.1

        sipper_duration = protocol.get('sipper_duration', 10) or 10

        # Add sipper periods
        _add_sipper_periods(ax, sipper_times, sipper_duration)

        # Plot active presses (green lines)
        if active_presses:
            ax.eventplot([active_presses], lineoffsets=0, linelengths=0.8,
                         linewidths=2.0, colors=COLORS['active_press'])

        # Plot inactive presses (red lines)
        if inactive_presses:
            ax.eventplot([inactive_presses], lineoffsets=0, linelengths=0.8,
                         linewidths=1.5, colors=COLORS['inactive_press'])

        # Plot licks as black lines
        if licks:
            ax.eventplot([licks], lineoffsets=0, linelengths=0.8,
                         linewidths=1.0, colors=COLORS['lick'], zorder=5)

        # Add 100-lick criterion line
        _add_lick_criterion_line(ax, licks)

        # Configure axes - tight to line heights
        ax.set_xlim(0, session_duration if session_duration > 0 else 3600)
        ax.set_ylim(-0.5, 0.5)
        ax.set_yticks([])

        # Clean up spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color(COLORS['axis'])
        ax.spines['bottom'].set_linewidth(0.5)

        # Gridlines
        ax.grid(True, axis='x', linestyle=':', alpha=0.3, color=COLORS['axis'])
        ax.tick_params(axis='x', colors=COLORS['axis'], labelsize=8)

        # Only show x-label on bottom plot
        if i == n_sessions - 1:
            ax.set_xlabel('Time (seconds)', fontsize=10, color=COLORS['axis'])

        # Add title with session info
        header = data.get('header', {})
        title = _create_title(header, protocol)
        if title:
            ax.set_title(title, fontsize=10, color=COLORS['axis'], pad=5, loc='left')

        # Add pass/fail badge if info is available
        if pass_statuses and i < len(pass_statuses):
            info = pass_statuses[i]
            _add_pass_status_badge(ax, info['passed'], info['pass_status'])

    plt.tight_layout()
    return fig, list(axes)
