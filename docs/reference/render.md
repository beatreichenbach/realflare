# Render
!!! info

    Parameters marked with a `*` will change in future versions.

## Output
`output_path`: Path for the final image to be written to. Use `$F4` for padding

`colorspace`: ACES based colorspace name

## Quality
`resolution`: Resolution of the final image

`bin_size *`: Size of the tiles used in the rasterizer

`subdivisions *`: The amount of anti aliasing subdivisions. Only supported options are 1, 2, 4, 8

> **Important**: During Pre-Release don't change the bin_size and keep the resolution a multiple of bin_size. These parameters will be simplified and changed in the future.

### Rays
`wavelength_count`: Amount of wavelengths used to trace through the lens system. Wavelengths are automatically chosen to cover the visible spectrum. Usually only 4 or 5 wavelengths need to be traced to give good results.

`wavelength_sub_count`: Amount of wavelengths that are interpolated during rasterization. Usually 8 give good results.

`grid_count`: Amount of points on the grid of rays that is traced through the lens system. Previews can look okay with 32 while final renders might need 64-128.

`grid_length`: Length of the grid of rays that is traced through the lens system. The grid is ideally as small as possible. Start with a value that is larger than the height of the lens (for example 50mm, that's the height not length of the lens) and go smaller until ghosts are not cut off anymore.

### Starburst
`resolution`: Resolution of the Starburst aperture and pattern

`samples *`: Amount of samples for the pattern renderer

### Ghost
`resolution`: Resolution of the Ghost aperture and pattern

## Debug
`disable_starburst`: Disable the Starburst pattern in the final image

`disable_ghosts`: Disable the Ghosts in the final image

`debug_ghosts`: Only render one Ghost in the final image

`debug_ghost`: Index of the Ghost that should be rendered

## Diagram
### Renderer
`resolution`: Resolution of the diagram

### Rays
`debug_ghost`: Index of the Ghost that should be rendered

`light_position`: Relative vertical position of the light source

`grid_count`: Amount of points on the grid of rays that is traced through the lens system

`grid_length`:Length of the grid of rays that is traced through the lens system

`column_offset`: Index offset of the column of rays in the grid to visualize
