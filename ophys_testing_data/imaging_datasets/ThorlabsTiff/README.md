# Thor 

## single_channel_single_plane

This folder/directory contains data that is generated with the `ThorImage®LS` software. The specifications can be found on their page [here](https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=9072#ad-image-0).

Note, that the empahsis is on the `ThorImage®LS` software, which is a software that is used to control the `Thorlabs` microscope. It it is possible that the the researcher uses other software (e.g. ScanImage) to control the acquisition with the microscope and the tiff data will be saved with a different bytes layout.

The data was kindly contributed by Eivind Hennestad and Anna R. Chambers then h.mayorquin@gmail.com stubed the files to reduce their size. The stubbed files were generated with the (first revision) the fllowing gist:

https://gist.github.com/h-mayorquin/0b99b241556f89580dc84ae0a7d0d1cf

Both the embedded ome metadata as well as the Experiment.xml specification were modified to account for the change on the number of frames.