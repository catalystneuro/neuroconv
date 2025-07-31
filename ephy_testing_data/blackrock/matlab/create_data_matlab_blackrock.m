%This script creates a mat file with spikes and LFP channels 1-8 of one
%data set supplied by Blackrock Microsystems that conforms to File
%Specification 2.3.
%
%The matlab code for loading data was originally provided through Blackrock
%Microsystems and was slightly modified.
%TODO: Update to newer versions of matlab file loaders provided by Blackrock.
%
%The result FileSpec2.3001.mat is used in the IO test :
% test_compare_blackrockio_with_matlabloader_V23
%
%Contents of data file:
%Raw recording on Channels 1-8
%Spike signal on Odd Channels (1-7)
%Recording on Analong Inputs 1 and 2
%Signal on Analog Input 2
%Three Comments Approximately 10 Seconds Apart
%Intermittent and Randomized Digital Signal
%No Serial Data
%No Tracking Data


openNEV('../FileSpec2.3001.nev','read','e:1','u:0','nosave','noparse');
openNSx('../FileSpec2.3001.ns5','e:1:8','read');


%get unit data
ts=NEV.Data.Spikes.Timestamps;
el=NEV.Data.Spikes.Electrode;
un=NEV.Data.Spikes.Unit;
wf=NEV.Data.Spikes.Waveform;

%load LFP matrix
lfp=NS5.Data;

%select units on el. 1-7
ts=ts(el>=1 & el<=7);
un=un(el>=1 & el<=7);
el=el(el>=1 & el<=7);

%marker
mts=NEV.Data.SerialDigitalIO.TimeStamp;
mid=NEV.Data.SerialDigitalIO.UnparsedData;

save('../FileSpec2.3001.mat','lfp','ts','el','un','wf','mts','mid');

