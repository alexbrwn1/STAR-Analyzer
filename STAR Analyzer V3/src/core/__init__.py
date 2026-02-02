"""Core business logic modules for STAR Analyzer V3."""

from .data_models import (
    SessionMetadata,
    ScalarVariables,
    TimestampArrays,
    ProtocolInfo,
    ParseWarning,
    MedPCSession,
    Cohort,
    Stage,
    PassStatus,
    SessionResult,
    AnimalState,
)
from .parser import (
    ParseError,
    MedPCParser,
    parse_medpc_file,
    parse_multiple_files,
    extract_protocol_info,
    detect_training_stage,
    get_session_display_name,
)
from .file_discovery import (
    discover_medpc_files,
    is_medpc_file,
    extract_filename_info,
    group_files_by_folder,
    group_files_by_subject,
    group_files_by_date,
)
from .tracker import (
    CohortTracker,
    check_pass_criteria,
    parse_date_from_filename,
    parse_date_from_header,
    generate_next_day_report,
)
from .session_manager import (
    SessionManager,
    ParsedSession,
)
from .plotting import (
    create_raster_plot,
    create_raster_plot_enhanced,
    create_multi_raster_plot,
    save_raster_plot,
    create_legend,
    COLORS,
    PASS_BADGE_COLORS,
)

__all__ = [
    # Data models
    'SessionMetadata',
    'ScalarVariables',
    'TimestampArrays',
    'ProtocolInfo',
    'ParseWarning',
    'MedPCSession',
    'Cohort',
    'Stage',
    'PassStatus',
    'SessionResult',
    'AnimalState',
    # Parser
    'ParseError',
    'MedPCParser',
    'parse_medpc_file',
    'parse_multiple_files',
    'extract_protocol_info',
    'detect_training_stage',
    'get_session_display_name',
    # File discovery
    'discover_medpc_files',
    'is_medpc_file',
    'extract_filename_info',
    'group_files_by_folder',
    'group_files_by_subject',
    'group_files_by_date',
    # Tracker
    'CohortTracker',
    'check_pass_criteria',
    'parse_date_from_filename',
    'parse_date_from_header',
    'generate_next_day_report',
    # Session manager
    'SessionManager',
    'ParsedSession',
    # Plotting
    'create_raster_plot',
    'create_raster_plot_enhanced',
    'create_multi_raster_plot',
    'save_raster_plot',
    'create_legend',
    'COLORS',
    'PASS_BADGE_COLORS',
]
