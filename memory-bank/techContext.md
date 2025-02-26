# Technical Context

## Development Environment

### Python Support
- Python versions: >=3.9
- Key version constraints:
  - Python 3.9-3.12 supported
  - Python 3.8 support dropped
  - Type hints use modern syntax

### Core Dependencies
```toml
dependencies = [
    "numpy>=1.22.0",
    "jsonschema>=3.2.0",
    "PyYAML>=5.4",
    "scipy>=1.4.1",
    "h5py>=3.9.0",
    "hdmf>=3.13.0",
    "hdmf_zarr>=0.7.0",
    "pynwb>=2.7.0",
    "pydantic>=2.0.0",
    "typing_extensions>=4.1.0",
    "psutil>=5.8.0",
    "tqdm>=4.60.0",
    "pandas",
    "parse>=1.20.0",
    "click",
    "docstring-parser",
    "packaging",
    "referencing"
]
```

### Development Tools
- Black for code formatting
- Ruff for linting
- pytest for testing
- pre-commit hooks
- ReadTheDocs for documentation

## Technical Constraints

### Memory Management
- Large dataset handling requires streaming
- Memory usage monitoring with psutil
- Chunked data writing for efficiency
- Buffer size optimization

### Performance Considerations
- Piece-wise data reading
- Compression optimization
- Parallel processing where possible
- Cache management strategies

### File Format Support
- HDF5 backend (default)
- Zarr backend (optional)
- Format-specific dependencies
- Compression options

## Modality-Specific Requirements

### Electrophysiology (ecephys)
```toml
ecephys = [
    "spikeinterface>=0.102",
    "neo>=0.13.3",
    "pyedflib>=0.1.36",
    "MEArec>=1.8.0",
    "natsort>=7.1.1",
    "lxml>=4.6.5"
]
```

### Optical Physiology (ophys)
```toml
ophys = [
    "roiextractors>=0.5.10",
    "tifffile>=2023.3.21",
    "scanimage-tiff-reader>=1.4.1",
    "ndx-fiber-photometry"
]
```

### Behavior
```toml
behavior = [
    "ndx-pose>=0.2",
    "sleap-io>=0.0.2",
    "opencv-python-headless>=4.8.1.78",
    "ndx-events==0.2.1",
    "ndx-miniscope>=0.5.1"
]
```

### Text Data
```toml
text = [
    "openpyxl",
    "xlrd"
]
```

## Installation Options

### Basic Installation
```bash
pip install neuroconv
```

### Format-Specific Installation
```bash
pip install "neuroconv[format_name]"
```

### Modality-Specific Installation
```bash
pip install "neuroconv[modality_name]"
```

### Full Installation
```bash
pip install "neuroconv[full]"
```

## Development Setup

### Environment Setup
```bash
conda create --name neuroconv_dev python=3.9
conda activate neuroconv_dev
pip install -e ".[full,test,docs]"
```

### Testing Setup
```bash
pytest tests/
pytest tests/test_on_data  # requires test data
```

### Documentation Setup
```bash
cd docs
make html
```

## Technical Decisions

### Backend Selection
- HDF5 default for compatibility
- Zarr support for cloud storage
- Automatic chunking configuration
- Compression optimization

### Dependency Management
- Minimal core requirements
- Optional format dependencies
- Version constraints for stability
- Platform-specific requirements

### Code Organization
- Modality-based structure
- Clear separation of concerns
- Interface-based design
- Utility modules

### Testing Strategy
- Unit tests per interface
- Integration tests
- Format-specific tests
- Performance benchmarks

## Platform Support

### Operating Systems
- Linux (primary)
- Windows
- MacOS (including M1)

### Cloud Integration
- AWS support
- DANDI archive integration
- Globus transfers
- S3 compatibility

## Security Considerations

### Data Integrity
- Validation at multiple stages
- Checksums for transfers
- Error detection and recovery
- Safe file operations

### Access Control
- Local file system permissions
- Cloud credentials management
- API key handling
- Secure data transfer

## Monitoring and Debugging

### Logging
- Verbose mode for debugging
- Progress reporting
- Error tracking
- Performance metrics

### Error Handling
- Clear error messages
- Stack trace preservation
- Recovery mechanisms
- User guidance

## Future Considerations

### Scalability
- Cloud-native operations
- Distributed processing
- Memory optimization
- Performance profiling

### Maintainability
- Code documentation
- Type annotations
- Test coverage
- Dependency updates
