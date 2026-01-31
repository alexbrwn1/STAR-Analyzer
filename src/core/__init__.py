# STAR Analyzer Core Module
# GUI-independent logic for parsing Med-PC IV data files

# Note: Imports deferred to allow both package and direct script usage
__all__ = [
    'SessionMetadata',
    'ScalarVariables',
    'TimestampArrays',
    'MedPCSession',
    'Cohort',
    'MedPCParser',
    'parse_medpc_file',
    'discover_medpc_files',
    'scan_folder_recursive',
    'ExcelExporter',
]
