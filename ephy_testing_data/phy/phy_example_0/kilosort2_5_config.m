ops.NchanTOT            = 32;           % total number of channels (omit if already in chanMap file)
ops.Nchan               = 32;           % number of active channels (omit if already in chanMap file)
ops.fs                  = 32000.0;     % sampling rate

ops.datatype            = 'dat';  % binary ('dat', 'bin') or 'openEphys'
ops.fbinary             = fullfile('/net/bs-filesvr01/export/group/hierlemann/Temp/Alessio/make_test_sorted_data/sorting_output/kilosort2_5/recording.dat'); % will be created for 'openEphys'
ops.fproc               = fullfile(fpath, 'temp_wh.dat'); % residual from RAM of preprocessed data
ops.root                = fpath; % 'openEphys' only: where raw files are
% define the channel map as a filename (string) or simply an array
ops.chanMap             = fullfile('chanMap.mat'); % make this file using createChannelMapFile.m

% frequency for high pass filtering (300)
ops.fshigh = 150;  % high-pass more aggresively

% minimum firing rate on a "good" channel (0 to skip)
ops.minfr_goodchannels = 0.1;

% number of blocks to use for nonrigid registration
ops.nblocks = 5;

% spatial smoothness constant for registration
ops.sig = 20;

% threshold on projections (like in Kilosort1, can be different for last pass like [10 4])
ops.Th = [10, 4];

% how important is the amplitude penalty (like in Kilosort1, 0 means not used, 10 is average, 50 is a lot) 
ops.lam = 10;  

% splitting a cluster at the end requires at least this much isolation for each sub-cluster (max = 1)
ops.AUCsplit = 0.9; 

% minimum spike rate (Hz), if a cluster falls below this for too long it gets removed
ops.minFR = 0.1;

% number of samples to average over (annealed from first to second value) 
ops.momentum = [20 400]; 

% spatial constant in um for computing residual variance of spike
ops.sigmaMask = 30; 

% threshold crossings for pre-clustering (in PCA projection space)
ops.ThPre = 8;

%% danger, changing these settings can lead to fatal errors
% options for determining PCs
ops.spkTh           = -6;      % spike threshold in standard deviations (-6)
ops.reorder         = 1;       % whether to reorder batches for drift correction. 
ops.nskip           = 25;  % how many batches to skip for determining spike PCs

ops.CAR             = 1; % perform CAR

ops.GPU                 = 1; % has to be 1, no CPU version yet, sorry
% ops.Nfilt             = 1024; % max number of clusters
ops.nfilt_factor        = 4; % max number of clusters per good channel (even temporary ones) 4
ops.ntbuff              = 64;    % samples of symmetrical buffer for whitening and spike detection 64
ops.NT                  = 65600; % must be multiple of 32 + ntbuff. This is the batch size (try decreasing if out of memory).  64*1024 + ops.ntbuff
ops.whiteningRange      = 32; % number of channels to use for whitening each channel
ops.nSkipCov            = 25; % compute whitening matrix from every N-th batch
ops.scaleproc           = 200;   % int16 scaling of whitened data
ops.nPCs                = 3; % how many PCs to project the spikes into
ops.useRAM              = 0; % not yet available

%%