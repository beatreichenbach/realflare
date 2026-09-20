# Engine

This package contains the engine that computes and renders the individual parts of a flare.

## Pipeline

Flare uses a compute-shader-based pipeline:

1. **Preprocessing** — Bounding boxes, reflectance, area variance per ghost element
2. **Raytracing** — Spectral rays traced through the lens system (390-730nm)
3. **Flare computation** — Ghost images, diffraction, starburst effects
4. **Composition** — All layers combined with OCIO color management
5. **Output** — Output images (exr, jpg, png, etc.)

## Color

### Convert spectral distribution to XYZ values

Integrate the product of the spectral distribution (reflectance) R, the illuminant I,
and the standard observer function CMFS:
```
XYZ = Σ (R(λ) * I(λ) * CMFS(λ))
```

Normalize to the white point (Y = 100):
```
k = 100 / Σ (I(λ) * CMFS_Y(λ))
XYZ = k * XYZ
```
