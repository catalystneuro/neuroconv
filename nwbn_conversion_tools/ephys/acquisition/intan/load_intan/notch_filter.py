#! /bin/env python
#
# Michael Gibson 27 April 2015

import math
import numpy as np

def notch_filter(input, fSample, fNotch, Bandwidth):
    """Implements a notch filter (e.g., for 50 or 60 Hz) on vector 'input'.

    fSample = sample rate of data (input Hz or Samples/sec)
    fNotch = filter notch frequency (input Hz)
    Bandwidth = notch 3-dB bandwidth (input Hz).  A bandwidth of 10 Hz is
    recommended for 50 or 60 Hz notch filters; narrower bandwidths lead to
    poor time-domain properties with an extended ringing response to
    transient disturbances.

    Example:  If neural data was sampled at 30 kSamples/sec
    and you wish to implement a 60 Hz notch filter:

    out = notch_filter(input, 30000, 60, 10);
    """

    tstep = 1.0/fSample
    Fc = fNotch*tstep

    L = len(input)

    # Calculate IIR filter parameters
    d = math.exp(-2.0*math.pi*(Bandwidth/2.0)*tstep)
    b = (1.0 + d*d) * math.cos(2.0*math.pi*Fc)
    a0 = 1.0
    a1 = -b
    a2 = d*d
    a = (1.0 + d*d)/2.0
    b0 = 1.0
    b1 = -2.0 * math.cos(2.0*math.pi*Fc)
    b2 = 1.0

    out = np.zeros(len(input))
    out[0] = input[0]
    out[1] = input[1]
    # (If filtering a continuous data stream, change out[0:1] to the
    #  previous final two values of out.)

    # Run filter
    for i in range(2,L):
        out[i] = (a*b2*input[i-2] + a*b1*input[i-1] + a*b0*input[i] - a2*out[i-2] - a1*out[i-1])/a0

    return out
