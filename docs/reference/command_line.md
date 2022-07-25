# Command Line

To render out sequences of frames realflare provides a command line interface `cli`. The basic usage expects a project file `.json` and frames to render.

`python -m realflare [options]`

| Option            | Description                                                                                                                                                                                                                                                                     |
|-------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `--arg "A V V"`   | argument being interpolated from frame-start to frame-end.<br/>Use the full path to the property in the config with values that can be converted to the type in python. Make sure to not include any spaces.<br/>For example: `--arg "flare.light_position [0.8,-0.8] [0.6,1]"` |
| `--frame-start F` | start frame                                                                                                                                                                                                                                                                     |
| `--frame-end F`   | end frame                                                                                                                                                                                                                                                                       |
| `--colorspace S`  | the output colorspace.<br/>For example `--colorspace "ACES - ACEScg"`                                                                                                                                                                                                           |
| `--gui`           | run the application in gui mode                                                                                                                                                                                                                                                 |
| `--output S`      | the output image path. Use `$F4` to replace frame numbers.<br/>For example: `--output render.$F4.exr`                                                                                                                                                                           |
| `--project S`     | the project to render the flare, a path to a `.json` file                                                                                                                                                                                                                       |


!!! info

    When specifying arguments to animate the flare, the full path of the parameter with respect to the flare needs to be given.
    To find the argument names check the project.json file. `Another example: flare.ghost.aperture.fstop`

Example usage:
```
venv\Scripts\python.exe -m realflare --frame-start 1 --frame-end 100 --project %UserName%\.realflare\project.json --arg "flare.light_position [0.8,-0.8] [0.6,1]" --output render/nikon_v003/render.$F4.exr
```
