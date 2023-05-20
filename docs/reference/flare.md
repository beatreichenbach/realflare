# Flare
The flare parameters can be stored in a preset and control the artistic look of the lens flare.

!!! info

    Parameters marked with a `*` will change in future versions.

## Light
`light_position`: Position of the light source relative to the image

## Lens
`sensor_size`: Size of the sensor in mm

`lens_model_path *`: File path of the lens model `.json` file 

`glasses_path *`: Folder path containing glass `.yml` files. Each lens element specifies a refractive index and Abbe number. Using those values the renderer finds the glass with the closest values and uses that to caluclate the dispersion. Different manufacturers might have glasses with different qualities that give unique looks.

`abbe_nr_adjustment`: Offset for all [Abbe numbers](https://en.wikipedia.org/wiki/Abbe_number) in the lens model. This can be used to add more or less dispersion to the glasses. Adjusting this value overrides the lens model and is here to for creative experimentation.

`coating_lens_elements`: List of [anti-reflective coatings](https://en.wikipedia.org/wiki/Anti-reflective_coating) for lens elements in a lens model. The *refractive index* depends on the material used for the coating (for example MgF2 with an index of 1.38.) The *wavelength* is the wavelength in nm that the coating is optimized for to reduce reflection.

## Starburst
The starburst pattern is the bright glare that appears where the light source is.

`aperture`:  Aperture Parameters

`intensity`: Intensity of the Starburst pattern

`lens_distance`: Distance from the sensor picking up the pattern to the aperture that is producing it

`blur`: Blur amount

`rotation`: Rotation amount

`rotation_weighting`: Weighting towards 1 will make the values on the outside of the rotation brighter

`fadeout`: Range (*from* and *to* of the radius) of the fadeout. To make sure there are no visible edges a radial fade is applied to the output.

`scale`: Overall scale of the Starburst pattern on the final image

## Ghost
`aperture`:  Aperture Parameters

`fstop *`: Temporary value to control the amount of the frft applied to the ghost. Controls the look of the Ghost ringing for now

`wavelength *`: Used internally
