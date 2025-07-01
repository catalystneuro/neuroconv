Recording date: 5-19-2022
Contact: Graham Findlay (gfindlay@wisc.edu)
Probes: 2x Neuropixel 1.0 submerged in ACSF.
SpikeGLX version: v.20201103

Every SpikeGLX run consists of 2 probes (imec0 & imec1) x 2 cycles (g0 & g1) x 2 t-files (t0 & t1).

### SpikeGLX Runs

- 5-19-2022-CI0
  - t-files are continuous: 10ms each, with a 0s inter-file interval.
  - Folder-per-probe organization.
- 5-19-2022-CI1
  - t-files are continuous: 10ms each, with a 0s inter-file interval.
  - Single-folder organization.
- 5-19-2022-CI2
  - t-files are discontinuous: 10ms each with a 1s inter-file interval.
  - Folder-per-probe organization.
- 5-19-2022-CI3
  - t-files are discontinuous: 10ms each with a 1s inter-file interval.
  - Single-folder organization.
- 5-19-2022-CI4
  - t-files are overlapping: 20ms each with 10ms overlap.
  - Folder-per-probe organization.
- 5-19-2022-CI4
  - t-files are overlapping: 20ms each with 10ms overlap.
  - Single-folder organization.

### CatGT-processed files

- CatGT-A
  - This is a concatenation of both t-files from the first cycle ONLY (i.e. _g0_t0 + g0_t1) of 5-19-2022-CI0. The output uses folder-per-probe organization.
  - Cmdline: `CatGT -dir=/path/to/5-19-2022-CI0 -run=5-19-2022-CI0 -g=0 -t=0,1 -prb_fld -ap -lf -prb=0:1 -no_auto_sync -zerofillmax=0 -dest=/path/to/CatGT-A -out_prb_fld`
- CatGT-B
  - Like CatGT-A, this is a concatenation of both t-files from the first cycle ONLY of 5-19-2022-CI0, but the output uses single-folder organization.
  - Cmdline: `CatGT -dir=/path/to/5-19-2022-CI0 -run=5-19-2022-CI0 -g=0 -t=0,1 -prb_fld -ap -lf -prb=0:1 -no_auto_sync -zerofillmax=0 -dest=/path/to/CatGT-B`
- CatGT-C
  - This is a concatenation of both t-files from BOTH cycles (i.e. _g0_t0 + g0_t1 + g1_t0 + g1_t1) of 5-19-2022-CI0. The output uses folder-per-probe organization.
  - Cmdline: `CatGT -dir=/path/to/5-19-2022-CI0 -run=5-19-2022-CI0 -g=0,1 -t=0,1 -prb_fld -ap -lf -prb=0:1 -no_auto_sync -zerofillmax=0 -dest=/path/to/CatGT-C -out_prb_fld`
- CatGT-D
  - Like CatGT-C, this is a concatenation of both t-files from BOTH cycles of 5-19-2022-CI0, but the output uses single-folder organization.
  - Cmdline: `CatGT -dir=/path/to/5-19-2022-CI0 -run=5-19-2022-CI0 -g=0,1 -t=0,1 -prb_fld -ap -lf -prb=0:1 -no_auto_sync -zerofillmax=0 -dest=/path/to/CatGT-D`
- CatGT-E
  - This is a concatenation of both t-files from both cycles of 5-19-2022-CI2. The output uses folder-per-probe organization.
  - Cmdline: `CatGT -dir=/path/to/5-19-2022-CI2 -run=5-19-2022-CI2 -g=0,1 -t=0,1 -prb_fld -ap -lf -prb=0:1 -no_auto_sync -zerofillmax=0 -dest=/path/to/CatGT-E -out_prb_fld`
- Supercat-A
  - This is a concatenation of CatGT-A and CatGT-E. The output uses folder-per-probe organization.
  - Cmdline: `CatGT -prb_fld -ap -lf -prb=0:1 -no_auto_sync -supercat={/path/to/CatGT-A,catgt_5-19-2022-CI0_g0}{/path/to/CatGT-E,catgt_5-19-2022-CI2_g0} -dest=/path/to/Supercat-A -out_prb_fld`

Notes on CatGT options used:
  - CatGT normally preserves the real-world duration of the recording by zero-filling gaps between t-files. In order to keep file sizes here as small as possible, we use `zerofillmax=0` to prevent this behavior.
  - Files are so short that they include no sync edges, and I use a custom sync scheme anyways. So files are processed with `-no_auto_sync`.
