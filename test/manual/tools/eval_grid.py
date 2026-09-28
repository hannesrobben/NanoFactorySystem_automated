from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import maximum_filter
from skimage.restoration import unwrap_phase

from nanofactorysystem import HoloContainer
from nanofactorysystem.hologram.reconstruct import locateOrder, getField, shiftSpectrum
from nanofactorysystem.image import functions as image


def get_phase(file):
    dc = HoloContainer(file=file)
    size = 16
    img = dc.img
    print(img.shape)
    fx, fy, rmax, weight = locateOrder(img, size)
    field = getField(img, fx, fy, rmax)
    print(field.shape)
    phase = np.angle(field)
    phase = unwrap_phase(phase)
    #phase = np.abs(field)
    return phase

nx = 5
ny = 5
off = 0
dt = 1.0
path = Path(f"./.test/grid-{dt:.1f}-{off:d}-{nx:d}x{ny:d}")

file = str(Path(path, "pre_holo.zdc"))
holo = HoloContainer(file=file).img
fx, fy, rmax, weight = locateOrder(holo, 16)
holo = holo.astype(np.float64)
spectrum = np.fft.rfft2(holo)
spectrum = shiftSpectrum(spectrum, fx, fy, rmax)
simg = np.abs(spectrum)
simg = image.normcolor(simg)
image.write("grid.png", simg)







phase0 = get_phase(str(Path(path, "pre_holo.zdc")))
phase1 = get_phase(str(Path(path, "post_holo.zdc")))

diff = phase1-phase0
diff = image.crop(diff, 640)
#diff = image.blur(diff, 2)
h, w = diff.shape

size = 60
img = -diff
img -= img.mean()
maxmask = (maximum_filter(img, size=size) == img)
points = np.unravel_index(np.nonzero(maxmask.ravel()), maxmask.shape)
points = np.concatenate(points, axis=0).T
points[:,0] -= h // 2
points[:,1] -= w // 2
print(len(points))

print(diff.min(), diff.max())
simg = image.normcolor(diff)
color = image.CV_BLUE
for y, x in points:
    value = img[y+h//2,x+w//2]
    print(x, y, value)
    #r = round(value*size//2)
    #simg = image.drawCircle(simg, x, y, r, color, thickness=1)
    simg = image.drawCircle(simg, x, y, size//2, color, thickness=1)

#image.write("grid.png", simg)
plt.imshow(simg)
plt.show()