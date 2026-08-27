# Say which SLEAP track is empty instead of failing inside numpy

When running #1990 across 35 public `.slp` files, 50 of the 122 convertible tracks failed, every one of them because the file declares a track that no frame carries an instance for, so `np.stack` got nothing to stack and the `ValueError` named neither the track nor the file. This PR raises where the selection is made instead, naming the track and the ones that do carry instances.
