import numpy as np
import axographio

names = ['Time (s)', 'Data 1 (V)', 'Data 2 (V)']

t = np.arange(0, 10, 0.01)
data1 = np.sin(1*t)
data2 = np.cos(2*t)

f1 = axographio.file_contents(names, [t, data1, data2])
f1.write('written-by-axographio-without-linearsequence.axgx')

f2 = axographio.file_contents(names, [axographio.aslinearsequence(t), data1, data2])
f2.write('written-by-axographio-with-linearsequence.axgx')
