# Active Context

## Current Development Focus

### Version 0.7.0 (Upcoming)
Based on latest CHANGELOG.md:

#### Active Changes
1. **Interface Behavior Changes**
   - Interfaces and converters now have `verbose=False` by default
   - Added metadata and conversion_options to temporal alignment
   - Deprecations in ecephys pipeline

2. **Bug Fixes**
   - Fixed append mode behavior in run_conversion
   - Improved dataset chunking recommendations

3. **Feature Additions**
   - Updated ndx-pose support for DeepLabCut and LightningPose
   - Added first draft of .clinerules

4. **Improvements**
   - Simplified writing process
   - Added Returns section to getter docstrings
   - Better chunking defaults for ElectricalSeries
   - Support for Spikeinterface 0.102
   - Ophys interfaces now call get_metadata by default
   - Support for hdmf 4.0 and numpy 2.0

### Recent Changes (v0.6.7)

1. **Bug Fixes**
   - Fixed chunking bug with hdmf
   - Added description to inter-sample-shift for SpikeGLX

2. **Improvements**
   - Better error messages for untyped parameters
   - Improved naming for multi-probe ElectrodeGroups
   - Better error detection for group mismatches
   - Fixed metadata bug in IntanRecordingInterface
   - Removed source validation from interface initialization

## Active Decisions

### Technical Decisions
1. **Default Settings**
   - Verbose mode now off by default
   - Automatic metadata retrieval for ophys
   - Improved chunking patterns

2. **Deprecations**
   - Removing old ecephys pipeline options
   - Transitioning compression settings
   - Moving to newer temporal alignment methods

3. **Architecture Changes**
   - Simplified writing process
   - Better error handling
   - Improved validation flow

### Development Priorities

1. **Short Term**
   - Bug fixes for chunking and metadata
   - Support for latest dependencies
   - Documentation improvements

2. **Medium Term**
   - Complete ecephys pipeline updates
   - Enhance temporal alignment
   - Improve error messages

3. **Long Term**
   - Full hdmf 4.0 integration
   - Enhanced numpy 2.0 support
   - Expanded format support

## Next Steps

### Immediate Tasks
1. **Bug Fixes**
   - Address remaining chunking issues
   - Fix metadata edge cases
   - Resolve validation concerns

2. **Feature Completion**
   - Complete temporal alignment updates
   - Finalize ecephys deprecations
   - Implement new chunking defaults

3. **Documentation**
   - Update API documentation
   - Add new examples
   - Improve error messages

### Upcoming Work
1. **Technical Improvements**
   - Optimize chunking patterns
   - Enhance validation system
   - Improve error handling

2. **User Experience**
   - Better default settings
   - Clearer error messages
   - Improved documentation

3. **Infrastructure**
   - Support latest dependencies
   - Enhance testing framework
   - Improve CI/CD pipeline

## Active Considerations

### Technical Challenges
1. **Performance**
   - Chunking optimization
   - Memory efficiency
   - Processing speed

2. **Compatibility**
   - Multiple format support
   - Version dependencies
   - Platform differences

3. **Usability**
   - Error clarity
   - Documentation quality
   - Default settings

### User Impact
1. **Breaking Changes**
   - Verbose mode default
   - Compression settings
   - Interface initialization

2. **Improvements**
   - Better error messages
   - Automatic metadata
   - Simplified processes

3. **Migration Path**
   - Clear deprecation warnings
   - Migration documentation
   - Backward compatibility

## Current Status

### Stable Features
- Core conversion pipeline
- Basic format support
- Metadata handling
- File validation

### In Development
- Enhanced temporal alignment
- Improved chunking system
- Updated documentation
- New format support

### Known Issues
- Chunking edge cases
- Metadata validation complexities
- Deprecation transitions
- Documentation gaps

### Future Plans
- Expanded format support
- Enhanced performance
- Better error handling
- Improved documentation
