function NSx = openNSx(varargin)

%%Opens an NSx file for reading, returns all file information in a NSx
% structure. Works with File Spec 2.1 and 2.2.
% Use OUTPUT = openNSx(fname, 'read', 'report', 'electrodes', 'duration', 'mode', 'precision').
%
% All input arguments are optional. Input arguments can be in any order.
%
%   fname:        Name of the file to be opened. If the fname is omitted
%                 the user will be prompted to select a file.
%                 DEFAULT: Will open Open File UI.
%
%   'read':       Will read the data in addition to the header information
%                 if user passes this argument.
%                 DEFAULT: will only read the header information.
%
%   'report':     Will show a summary report if user passes this argument.
%                 DEFAULT: will not show report.
%
%   'electrodes': User can specify which electrodes need to be read. The
%                 number of electrodes can be greater than or equal to 1
%                 and less than or equal to 128. The electrodes can be
%                 selected either by specifying a range (e.g. 20:45) or by
%                 indicating individual electrodes (e.g. 3,6,7,90) or both.
%                 This field needs to be followed by the prefix 'e:'. See
%                 example for more details.
%                 DEFAULT: will read all existing channels.
%
%   'duration':   User can specify the beginning and end of the data
%                 segment to be read. If the start time is greater than the
%                 length of data the program will exit with an error
%                 message. If the end time is greater than the length of
%                 data the end packet will be selected for end of data. The
%                 user can specify the start and end values by comma
%                 (e.g. [20,50]) or by a colon (e.g. [20:50]). To use this
%                 argument the user must specify the [electrodes] or the
%                 interval will be used for [electrodes] automatically.
%                 This field needs to be followed by the prefix 't:'. See
%                 example for more details.
%                 DEFAULT: will read the entire file.
%
%   'mode':       The user can specify the mode of duration in [duration],
%                 such as 'sec', 'min', 'hour', or 'sample'. If 'sec' is
%                 specified the numbers in [duration] will correspond to
%                 the number of seconds. The same is true for 'min', 'hour'
%                 and 'sample'.
%                 DEFAULT: will be set to 'sample'.
%
%   'precision':  The data storage class can be any format known by
%                 MATLAB such as 'double', 'int16', 'int'.
%                 This field needs to be followed by the prefix 'p:'. See
%                 example for more details.
%                 DEFAULT: will be set to 'double'
%
%   OUTPUT:       Contains the NSx structure.
%
%   Example:
%
%   openNSx('report','read','c:\data\sample.ns5', 'e:15:30', 't:3:10', 'min', 'p:int16');
%
%   In the example above, the file c:\data\sample.ns5 will be used. A
%   report of the file contents will be shown. The data will be read from
%   electrodes 15 through 50 in the 3-10 minute time interval. The data
%   is saved in 'int16' type.
%   If any of the arguments above are omitted the default values will be used.
%
%   Kian Torab
%   kian.torab@utah.edu
%   Department of Bioengineering
%   University of Utah
%   Version 2.1.0 - March 22, 2010

NSxver = '2.1.0';
disp(['openNSx version ' NSxver])

%% Defining the NSx data structure and sub-branches.
NSx             = struct('MetaTags',[],'Data',[]);
NSx.MetaTags    = struct('FileTypeID',[],'ChannelCount',[],'SamplingFreq',[],'ChannelID',[],'Version',[],'ElecLabel',[],'CreateDateTime',[]);

%% Validating the input arguments. Exit with error message if error occurs.
for i=1:length(varargin)
    inputArgument = varargin{i};
    if strcmpi(inputArgument, 'report')
        Report = inputArgument;
    elseif strcmpi(inputArgument, 'read')
        ReadData = inputArgument;
    elseif strncmp(varargin{i}, 't:', 2)
        colonIndex = find(inputArgument(3:end) == ':');
        StartPacket = str2num(inputArgument(3:colonIndex+1));
        EndPacket = str2num(inputArgument(colonIndex+3:end));
        if min(varargin{i})<1 || max(varargin{i})>128
            display('The electrode number cannot be less than 1 or greater than 128.');
            clear variables;
            if nargout; NSx = []; end
            return;
        end
    elseif strncmp(varargin{i}, 'e:', 2)
        Elec = str2num(inputArgument(3:end)); %#ok<ST2NM>
    elseif strncmp(varargin{i}, 'p:', 2)
        Precision = inputArgument(3:end); % precision for storage
    elseif strfind(' hour min sec sample ', [' ' inputArgument ' ']) ~= 0
        TimeScale = inputArgument;
    else
        temp = inputArgument;
        if length(temp)>3 && strcmpi(temp(end-3),'.')
            fname = inputArgument;
            if exist(fname, 'file') ~= 2
                display('The file does not exist.');
                clear variables;
                if nargout; NSx = []; end
                return;
            end
        else
            display(['Invalid argument ''' inputArgument ''' .']);
            clear variables;
            if nargout; NSx = []; end
            return;
        end
    end
end

%% Popup the Open File UI. Also, process the file name, path, and extension
%  for later use, and validate the entry.
if ~exist('fname', 'var')
    [fname, path] = uigetfile('D:\Data\*.ns*');
    if fname == 0
        clear variables;
        if nargout; NSx = []; end
        return;
    end
    fext = fname(end-3:end);
else
    [path, fname, fext] = fileparts(fname);
    fname = [fname fext];
end
if fname==0; return; end;

tic;

%% Give all input arguments a default value. All input argumens are
%  optional.
if ~exist('Report', 'var');      Report = 'noreport'; end
if ~exist('ReadData', 'var');    ReadData = 'noread'; end
if ~exist('StartPacket', 'var'); StartPacket = 0;     end
if ~exist('TimeScale', 'var');   TimeScale = 1;       end
if ~exist('Precision', 'var');   Precision = 'double';       end

%% Reading Basic Header from file into NSx structure.
% we use fullfile instead of [path '\' fname] to support nix platforms
FID                       = fopen(fullfile(path,fname), 'r', 'ieee-le');
NSx.MetaTags.FileTypeID   = fread(FID, [1,8] , 'uint8=>char');

% Validate the data file's File Spec.
if strcmp(NSx.MetaTags.FileTypeID, 'NEURALSG')                              % 2.1
    NSx.MetaTags.Version = '2.1';
    NSx.MetaTags.Label           = fread(FID, [1,16] , 'uint8=>char');
    NSx.MetaTags.SamplingFreq    = 30000/fread(FID, 1 , 'uint32=>double');
    ChannelCount                 = fread(FID, 1 , 'uint32=>double');
    NSx.MetaTags.ChannelID       = fread(FID, [ChannelCount 1], '*uint32');
    NSx.MetaTags.ChannelCount    = ChannelCount;
    fHeader = ftell(FID);
elseif strcmp(NSx.MetaTags.FileTypeID, 'NEURALCD')                          % 2.2, 2.3
    Major                        = num2str(fread(FID, 1  , 'uint8=>double'));
    Minor                        = num2str(fread(FID, 1  , 'uint8=>double'));
    NSx.MetaTags.Version         = [Major '.' Minor];
    fHeader                      = fread(FID, 1  , 'uint32=>double');
    NSx.MetaTags.Label           = fread(FID, [1,16]  , 'uint8=>char');
    NSx.MetaTags.Comments        = fread(FID, [1,256]  , 'uint8=>char');
    NSx.MetaTags.SamplingFreq    = 30000/fread(FID, 1 , 'uint32=>double' );
    NSx.MetaTags.Resolution      = fread(FID, 1 , 'uint32=>double' );
    NSx.MetaTags.CreateDateTime  = fread(FID, [1,8] , 'uint16=>double' );
    ChannelCount                 = fread(FID, 1       , 'uint32=>double' );
    NSx.MetaTags.ChannelCount    = ChannelCount;
    NSx.MetaTags.ChannelID       = zeros(ChannelCount, 1);
    NSx.MetaTags.ElecLabel       = char(zeros(ChannelCount, 16));         % Electrode label
    % now read external header
    for ii = 1:ChannelCount
        CC = fread(FID, [1,2]  , 'uint8=>char');
        if ~strcmp(CC, 'CC')
            display('Wrong extension header');
            fclose(FID);
            clear variables;
            return;
        end
        NSx.MetaTags.ChannelID(ii) = fread(FID, 1 , 'uint16=>double');
        NSx.MetaTags.ElecLabel(ii,:) = fread(FID, [1,16]  , 'uint8=>char');
        % We do not care about the rest now
        dummy = num2str(fread(FID, [46,1]  , 'uint8=>double')); % dummy
    end
    clear dummy;
    if fHeader ~= ftell(FID)
        display('Header file corrupted!');
        fHeader = ftell(FID);
    end
    fHeader = fHeader + 9; % to account for the data header
else
    display('This version of openNSx can only read File Specs 2.1 or 2.2');
    display(['The selected file label is ' NSx.MetaTags.FileTypeID '.']);
    fclose(FID);
    clear variables;
    if nargout; NSx = []; end;
    return;
end;
% find out number of data points
fseek(FID, 0, 'eof');
fData = ftell(FID);
fseek(FID, fHeader, 'bof');

%% Adjusts StartPacket and EndPacket based on what time setting (sec, min,
%  hour, or packets) the user has indicated in the input argument.
switch TimeScale
    case 'sec'
        StartPacket = StartPacket * NSx.MetaTags.SamplingFreq;
        EndPacket = EndPacket * NSx.MetaTags.SamplingFreq;
    case 'min'
        StartPacket = StartPacket * NSx.MetaTags.SamplingFreq * 60;
        EndPacket = EndPacket * NSx.MetaTags.SamplingFreq * 60;
    case 'hour'
        StartPacket = StartPacket * NSx.MetaTags.SamplingFreq * 3600;
        EndPacket = EndPacket * NSx.MetaTags.SamplingFreq * 3600;
    case 'sample'
        StartPacket = StartPacket - 1;
        EndPacket   = EndPacket - 1;
end

%% Validate StartPacket and EndPacket to make sure they do not exceed the
%  length of packets in the file. If EndPacket is over then the last packet
%  will be set for EndPacket. If StartPacket is over then will exist with an
%  error message.
NumofPackets = (fData-fHeader)/(2*ChannelCount);
if exist('EndPacket', 'var') && (EndPacket > NumofPackets)
    display('The time interval specified is longer than the data duration.');
    if StartPacket > NumofPackets
        disp('The starting packet is greater than the total data duration.');
        clear variables;
        if nargout; NSx = []; end
        return;
    end
    disp('The time interval specified is longer than the data duration.');
    disp('Last data point will be used instead.');
    disp('Press enter to continue...');
    pause;
    EndPacket = NumofPackets;
elseif ~exist('EndPacket', 'var')
    EndPacket = NumofPackets;
end
DataLength = EndPacket - StartPacket;
clear TimeScale

%% Displaying a report of basic file information and the Basic Header.
if strcmp(Report, 'report')
    disp( '*** FILE INFO **************************');
    disp(['File Path          = '  path]);
    disp(['File Name          = '  fname   ]);
    disp(['File Version       = '  NSx.MetaTags.Version   ]);
    disp(['Duration (seconds) = '  num2str(NumofPackets/NSx.MetaTags.SamplingFreq)]);
    disp(['Total Data Points  = '  num2str(NumofPackets)                   ]);
    disp(' ');
    disp( '*** BASIC HEADER ***********************');
    disp(['File Type ID       = '          NSx.MetaTags.FileTypeID      ]);
    disp(['Label              = '          NSx.MetaTags.Label           ]);
    disp(['Sample Resolution  = '  num2str(NSx.MetaTags.SamplingFreq)         ]);
    disp(['Electrodes Read    = '  num2str(NSx.MetaTags.ChannelCount)   ]);
end

%%
if ~exist('Elec', 'var');
    Elec = 1:ChannelCount;
end
Elec=Elec(Elec>=1 & Elec<=ChannelCount);
ReadElec = max(Elec)-min(Elec)+1;
if (ReadElec <= ChannelCount)
    if strcmp(ReadData, 'read')
        fseek(FID, StartPacket * 2 * ChannelCount + fHeader, 'bof');
        fseek(FID, (min(Elec)-1) * 2, 'cof');
        NSx.Data = fread(FID, [ReadElec DataLength-1], [num2str(ReadElec) '*int16=>' Precision], (ChannelCount-ReadElec) * 2);
    end
end
%% If user does not specify an output argument it will automatically create
%  a structure.
outputName = ['NS' fext(4)];
if (nargout == 0),
    assignin('caller', outputName, NSx);
end

if strcmp(Report, 'report')
    display(['The load time for ' outputName ' file was ' num2str(toc, '%0.1f') ' seconds.']);
end
fclose(FID);

end