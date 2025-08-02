Directory contains test data for early versions of Cheetah software, such as 4.0.2,
which had a shorter header containing a rounded sampling frequency without stating
microsPerSamp.

In these files, the number of microseconds between samples was always
a whole number of microseconds corresponding to the truncated inverse of the stated
sampling frequency in the header.

This limitation arose from the fact that the sampling was controlled by a 1 MHz
master clock on the ADC cards.
