# [CellExplorer](https://cellexplorer.org/) Datasets

The the datasets 1, 2 and 3 are a shortened versions of public datasets by provided by David Tingley

Original sources:
- `dataset_1`: https://buzsakilab.nyumc.org/datasets/TingleyD/DT8/20170311_684um_2088um_170311_134350/
- `dataset_2`: https://buzsakilab.nyumc.org/datasets/TingleyD/DT9/20170504_396um_0um_merge/
- `dataset_3`: https://buzsakilab.nyumc.org/datasets/TingleyD/DT9/20170519_864um_900um_merge/
- `dataset4` : https://buzsakilab.nyumc.org/datasets/PetersenP/CellExplorerExampleData/MS22/Peter_MS22_180629_110319_concat/

Note:
- `dataset_2` and `dataset_3` contain mat files with version different from mat version 5.
- `dataset_2`: `sessionInfo` is saved as mat version 7.3.
- `dataset_3`: `spikes.cellinfo` is saved as mat version 7.3
- `dataset_4`: is a stubbed version of the original dataset. The original dataset is is in the link indicated above. 
There are two folders inside, one saved in the old matlab format and other in the new one (hdf5). They were stubbed with the following program https://gist.github.com/h-mayorquin/576e54fae7ff2cf0d1255f15fe80a20c. The binary files
were stubbed by using a `SlicingRecorder`` in spikeinterface to the first 1000 frames
 