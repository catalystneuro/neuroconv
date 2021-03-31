Part 3, Automated Format Conversions
====================================

Conversion to NWB presents some challenges that come up again and again:

1. **Variety**. There is a large variety of proprietary formats in neurophysiology.
   Even within a single lab, you may have data from several different acquisition systems.
   Converting to NWB requires understanding how data is stored in that format,
   what metadata is present in the file, and where that metadata is within the proprietary
   files, as well as where they should go within NWB.
1. **Volume**. Neurophysiology data is large and the volume of individual session data
   is growing every year. HDF5 is designed to handle data at this scale, and has several
   tools that can help, including iterative read/write, chunking of large datasets,
   and streamlined compression/decompression. To dig into these tools yourself,
   see the PyNWB and MatNWB tutorials on advanced data I/O listed in the table above.

In order to make converting to NWB faster and less laborious (for our own team and for others),
we have developed an ecosystem of conversion tools that provide support for converting a
number of different proprietary formats to NWB. These tools handle the challenges of
variety and volume for the most common of data types.

Extracellular Electrophysiology
--------------------------------

A package within the SpikeInterface project called [SpikeExtractors](https://spikeinterface.readthedocs.io/en/latest/)
has been developed to read extracellular electrophysiological data
from a variety of proprietary formats, for both raw and spike-sorted data.
We worked with the development team to robustly handle the technical details
of converting from these formats to NWB through the SpikeExtractors interface.
SpikeExtractors also leverages advanced I/O tools to automatically chunk large
datasets and apply lossless compression that is transparent to the user but can
substantially reduce the size of the NWB file. This package does not support
every electrophysiology data type, but does support a large number of them -
at the time of this writing, 21 raw formats and 18 spike-sorted formats.
Many of these formats are supported through a wrapper around [python-neo](https://neo.readthedocs.io/en/latest/) reader classes.

For extracellular electrophysiology, we use the SpikeExtractors repository from the 
[SpikeInterface](http://spikeinterface.readthedocs.io/) 
project. To install this package, run

```bash
$ pip install spikeextractors
```

Below is a collection of simple, tested conversion scripts for common extracellular electrophysiology formats (click
 the triangle to expand):

<details>
<summary><b>Raw voltage traces</b></summary><blockquote>
<p>
<details>
<summary>Blackrock</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, BlackrockRecordingExtractor

rx = BlackrockRecordingExtractor("dataset_path")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>Intan</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, IntanRecordingExtractor

rx = IntanRecordingExtractor("intan_rhd_test_1.rhd")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>MEArec</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, MEArecRecordingExtractor

rx = MEArecRecordingExtractor("mearec_test_10s.h5")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>Neuralynx</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, NeuralynxRecordingExtractor

rx = NeuralynxRecordingExtractor("data_directory")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>Neuroscope</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, NeuroscopeRecordingExtractor

rx = NeuroscopeRecordingExtractor("data_file.dat")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>OpenEphys (legacy)</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, OpenEphysRecordingExtractor

rx = OpenEphysRecordingExtractor("data_folder")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>OpenEphys binary (Neuropixels)</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, OpenEphysNPIXRecordingExtractor

rx = OpenEphysNPIXRecordingExtractor("folder_path")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>Phy</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, PhyRecordingExtractor

rx = PhyRecordingExtractor("folder_path")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>SpikeGLX</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, SpikeGLXRecordingExtractor

rx = SpikeGLXRecordingExtractor("MySession_g0_t0.imec0.ap.bin")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        
</p>
</blockquote></details>
    
<details>
<summary><b>Spike-sorted data</b></summary><blockquote>
<p>
        

<details>
<summary>Blackrock</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor, BlackrockSortingExtractor

rx = BlackrockSortingExtractor("filename")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>Klusta</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor, KlustaSortingExtractor

rx = KlustaSortingExtractor("neo.kwik")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>MEArec</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor, MEArecSortingExtractor

rx = MEArecSortingExtractor("mearec_test_10s.h5")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>Phy</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor, PhySortingExtractor

rx = PhySortingExtractor("data_folder")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>Plexon</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor, 

rx = ("File_plexon_2.plx")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>Spyking Circus</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor, 

rx = ("file_or_folder_path")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>
        
</p>
</blockquote>
</details>

<br>

All of these conversions are tested against the 
[ephy_testing_data](https://gin.g-node.org/NeuralEnsemble/ephy_testing_data) GIN repository.

Optical Neurophysiology
------------------------
We also developed a sister-package, [RoiExtractors](https://github.com/catalystneuro/roiextractors), which does the same
for common raw and processed data types in optical neurophysiology, image stacks and regions of interest (ROIs).
Analogous to SpikeExtractors, RoiExtractors contains ImagingExtractors for reading image stacks and 
SegmentationExtractors for reading extracted ROIs saved from popular processing pipelines.

To install, run

```bash
$ pip install roiextractors
``` 

<details>
<summary><b>Imaging</b></summary><blockquote>
<p>
        

<details>
<summary>Tiff</summary><blockquote>
<p>

```python
from roiextractors import NwbImagingExtractor, TiffImagingExtractor

imaging_ex = TiffImagingExtractor("imaging.tiff")
NwbImagingExtractor.write_imaging(imaging_ex, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>Hdf5</summary><blockquote>
<p>

```python
from roiextractors import NwbImagingExtractor, Hdf5ImagingExtractor

imaging_ex = Hdf5ImagingExtractor("Movie.hdf5")
NwbImagingExtractor.write_imaging(imaging_ex, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>SBX</summary><blockquote>
<p>

```python
from roiextractors import NwbImagingExtractor, SbxImagingExtractor

imaging_ex = SbxImagingExtractor("scanbox_file.mat")
NwbImagingExtractor.write_imaging(imaging_ex, "output_path.nwb")
```
</p>
</blockquote></details>
        
</p>
</blockquote></details>
    
<details>
<summary><b>ROI Segmentation</b></summary><blockquote>
<p>
        

<details>
<summary>CaImAn</summary><blockquote>
<p>

```python
from roiextractors import NwbSegmentationExtractor, CaimanSegmentationExtractor

seg_ex = CaimanSegmentationExtractor("caiman_analysis.hdf5")
NwbSegmentationExtractor.write_segmentation(seg_ex, "output_path.nwb")
```
</p>
</blockquote></details>
        

<details>
<summary>Suite2p</summary><blockquote>
<p>

```python
from roiextractors import NwbSegmentationExtractor, Suite2pSegmentationExtractor

seg_ex = Suite2pSegmentationExtractor("segmentation_datasets/suite2p")
NwbSegmentationExtractor.write_segmentation(seg_ex, "output_path.nwb")
```
</p>
</blockquote></details>
        
</p>
</blockquote></details>

<br>


All format conversions listed here are tested against the 
[ophys_testing_data](https://gin.g-node.org/CatalystNeuro/ophys_testing_data) GIN repository.


Intracellular Electrophysiology
--------------------------------
Conversion of common intracellular electrophysiology data types to NWB is
supported by [IPFX](https://github.com/AllenInstitute/ipfx/blob/master/ipfx/x_to_nwb/Readme.md), developed by the Allen Institute.
This package has not yet been integrated into NWB Conversion Tools.

