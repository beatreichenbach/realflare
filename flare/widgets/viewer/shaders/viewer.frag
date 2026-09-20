uniform sampler2D image;

uniform Params {
    vec2 image_size;
    vec2 resolution;
    vec2 offset;
    float scale;
    float gain;
    uint channel;
    bool border;
};

in vec2 uv;
out vec4 rgba;

void main() {
    // Position in pixel
    vec2 pos = uv * resolution;

    // Apply pan and zoom
    vec2 transform = (pos - offset) / scale;

    // Image uv space
    vec2 image_uv = transform / image_size;

    rgba = texture(image, image_uv);

    // Select channel
    if (channel == 1u) {
        rgba = vec4(rgba.x, rgba.x, rgba.x, 1.0);
    } else if (channel == 2u) {
        rgba = vec4(rgba.y, rgba.y, rgba.y, 1.0);
    } else if (channel == 3u) {
        rgba = vec4(rgba.z, rgba.z, rgba.z, 1.0);
    } else if (channel == 4u) {
        rgba = vec4(rgba.w, rgba.w, rgba.w, 1.0);
    }

    // Gain
    rgba.xyz *= gain;

    // OCIO
    rgba = OCIOMain(rgba);

    if (border) {
        float border_width = 1.0 / scale;
        vec2 outside = step(vec2(0.0 - border_width), transform) * step(transform, image_size + border_width);
        vec2 inside = step(vec2(0.0), transform) * step(transform, image_size);
        bool frame = bool(outside.x * outside.y - inside.x * inside.y > 0.0);
        bool pattern = bool(mod(pos.x + pos.y, 5.0) > 3.0);

        if (frame && pattern) {
            rgba = vec4(0.25);
        }
    }
    rgba.w = 1;
}
