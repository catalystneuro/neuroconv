## Converting data to NWB
Below is a collection of simple conversion scripts that are all tested against small
proprietary examples files. They are all optimized to handle very large data by iteratively
steping through large files and read/writing them one piece at a time. They also leverage
lossless compression within HDF5, which allows you to make large datasets smaller without
losing any data. We have seen this reduce large datasets by up to 66%!


<details>
<summary>Extracellular electrophysiology</summary>

<br>
For extracellular electrophysiology, we use the SpikeExtractors repository from the
[SpikeInterface](http://spikeinterface.readthedocs.io/)
project. To install this package, run

```bash
$ pip install spikeextractors
```

All of the format listed below are tested against example dataset in the
[ephy_testing_data](https://gin.g-node.org/NeuralEnsemble/ephy_testing_data) GIN repository
maintained by the NEO team.
<blockquote>
<p>

<details>
<summary>Recording</summary><blockquote>
<p>


<details>
<summary>    Blackrock</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, BlackrockRecordingExtractor

rx = BlackrockRecordingExtractor("dataset_path")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    Intan</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, IntanRecordingExtractor

rx = IntanRecordingExtractor("intan_rhd_test_1.rhd")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    MEArec</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, MEArecRecordingExtractor

rx = MEArecRecordingExtractor("mearec_test_10s.h5")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    Neuralynx</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, NeuralynxRecordingExtractor

rx = NeuralynxRecordingExtractor("data_directory")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    Neuroscope</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, NeuroscopeRecordingExtractor

rx = NeuroscopeRecordingExtractor("data_file.dat")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    OpenEphys (legacy)</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, OpenEphysRecordingExtractor

rx = OpenEphysRecordingExtractor("data_folder")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    OpenEphys binary (Neuropixels)</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, OpenEphysNPIXRecordingExtractor

rx = OpenEphysNPIXRecordingExtractor("folder_path")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    Phy</summary><blockquote>
<p>

```python
from spikeextractors import NwbRecordingExtractor, PhyRecordingExtractor

rx = PhyRecordingExtractor("folder_path")
NwbRecordingExtractor.write_recording(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    SpikeGLX</summary><blockquote>
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
<summary>Sorting</summary><blockquote>
<p>


<details>
<summary>    Blackrock</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor, BlackrockSortingExtractor

rx = BlackrockSortingExtractor("filename")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    Klusta</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor, KlustaSortingExtractor

rx = KlustaSortingExtractor("neo.kwik")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    MEArec</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor, MEArecSortingExtractor

rx = MEArecSortingExtractor("mearec_test_10s.h5")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    Phy</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor, PhySortingExtractor

rx = PhySortingExtractor("data_folder")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    Plexon</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor,

rx = ("File_plexon_2.plx")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    Spyking Circus</summary><blockquote>
<p>

```python
from spikeextractors import NwbSortingExtractor,

rx = ("file_or_folder_path")
NwbSortingExtractor.write_sorting(rx, "output_path.nwb")
```
</p>
</blockquote></details>

</p>
</blockquote></details>

</p>
</blockquote></details>

<details>
<summary>Optical physiology</summary>

<br>
For optical physiology, we use the [RoiExtractors](https://roiextractors.readthedocs.io/en/latest/)
library developed by [CatalystNeuro](catalystneuro.com). To install, run

```bash
$ pip install roiextractors
```

All formats listed in the optical physiology section are tested against the
[ophys_testing_data](https://gin.g-node.org/CatalystNeuro/ophys_testing_data) GIN repository.
<blockquote>
<p>

<details>
<summary>Imaging</summary><blockquote>
<p>


<details>
<summary>    Tiff</summary><blockquote>
<p>

```python
from roiextractors import NwbImagingExtractor, TiffImagingExtractor

imaging_ex = TiffImagingExtractor("imaging.tiff")
NwbImagingExtractor.write_imaging(imaging_ex, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    Hdf5</summary><blockquote>
<p>

```python
from roiextractors import NwbImagingExtractor, Hdf5ImagingExtractor

imaging_ex = Hdf5ImagingExtractor("Movie.hdf5")
NwbImagingExtractor.write_imaging(imaging_ex, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    SBX</summary><blockquote>
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
<summary>Segmentation</summary><blockquote>
<p>


<details>
<summary>    CaImAn</summary><blockquote>
<p>

```python
from roiextractors import NwbSegmentationExtractor, CaimanSegmentationExtractor

seg_ex = CaimanSegmentationExtractor("caiman_analysis.hdf5")
NwbSegmentationExtractor.write_segmentation(seg_ex, "output_path.nwb")
```
</p>
</blockquote></details>


<details>
<summary>    Suite2p</summary><blockquote>
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

</p>
</blockquote></details>
