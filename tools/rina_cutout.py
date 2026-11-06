# green-screen cutout for generated 星餓りな illustrations: key + despill + edge colour from nearest solid pixel, trimmed to content
import sys, numpy as np
from PIL import Image
from scipy import ndimage
def cut(src, dst):
    a = np.asarray(Image.open(src).convert('RGB')).astype(np.float32); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    k = g - np.maximum(r, b); alpha = np.clip(1 - (k - 20) / 50, 0, 1)
    alpha = ndimage.binary_fill_holes(alpha > 0.5) * 0 + alpha  # keep soft edges
    lab, n = ndimage.label(alpha > 0.5); sizes = ndimage.sum(alpha > 0.5, lab, range(1, n + 1))
    keep = np.isin(lab, 1 + np.where(sizes > 0.02 * sizes.max())[0]); keep = ndimage.binary_dilation(keep, iterations=3)
    alpha = alpha * keep
    alpha = ndimage.gaussian_filter(ndimage.minimum_filter(alpha, 3), 0.7)
    solid = alpha > 0.95; _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True); e = ~solid
    g = np.minimum(g, np.maximum(r, b) + 4)
    r, g, b = [np.where(e, c[iy, ix], c) for c in (r, g, b)]
    out = np.dstack([r, g, b, alpha * 255]).clip(0, 255).astype(np.uint8)
    ys, xs = np.where(out[..., 3] > 8); pad = 8
    Image.fromarray(out, 'RGBA').crop((max(xs.min() - pad, 0), max(ys.min() - pad, 0), xs.max() + pad, ys.max() + pad)).save(dst)
if __name__ == '__main__': cut(sys.argv[1], sys.argv[2])
