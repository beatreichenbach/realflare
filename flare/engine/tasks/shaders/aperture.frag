#version 430 core

#define M_PI 3.14159265359f

uniform Params {
    // Shape
    vec2 resolution;
    vec2 shape_size;
    uint shape_blades;
    float shape_roundness;
    float shape_rotation;
    float shape_softness;

    // Grating
    float grating_strength;
    float grating_density;
    float grating_length;
    float grating_width;
    float grating_softness;

    // Scratches
    float scratches_strength;
    float scratches_density;
    float scratches_length;
    float scratches_width;
    float scratches_rotation;
    float scratches_rotation_variation;
    float scratches_softness;
    vec2 scratches_parallax;

    // Dust
    float dust_strength;
    float dust_density;
    float dust_radius;
    float dust_softness;
    vec2 dust_parallax;

    // Image
    vec2 image_size;
    float image_strength;
    float image_black;
    float image_white;
    float _pad[3];
};

uniform sampler2D image_texture;

out vec4 rgba;

vec2 wrap(vec2 value, float m) {
    return mod(m + mod(value, m), m);
}

float shape(
    vec2 position,
    vec2 size,
    uint blades,
    float roundness,
    float rotation,
    float softness
) {
    vec2 pos = position;
    pos = scale(pos, size);
    pos = rot(pos, rotation);

    // Blades
    float sdf = 0.0;
    for (uint i = 0u; i < blades; i++) {
        float angle = (float(i) / float(blades) + 0.25) * 2.0 * M_PI;
        vec2 axis = vec2(cos(angle), sin(angle));
        sdf = max(sdf, dot(axis, pos));
    }

    // Roundness
    // Match start position bottom: (-pos.x, -pos.y)
    // Fit into 0 - 1: + 0.5f
    float circular_gradient = atan(-pos.x, -pos.y) / (2.0 * M_PI) + 0.5;
    // Center sine: + 0.5f
    float blades_gradient = mod(circular_gradient * float(blades) + 0.5, 1.0);
    float roundness_gradient = sin(blades_gradient * M_PI);
    sdf += roundness_gradient * roundness;

    // Intensity
    float intensity = 1.0 - smoothstep(1.0 - softness, 1.0 + softness, sdf);

    return intensity;
}

float grating(
    vec2 position,
    vec2 size,
    float strength,
    float density,
    float length,
    float width,
    float softness
) {
    vec2 pos = position;
    pos = scale(pos, size);

    vec2 half_size = vec2(width, length * 2.0) / 2.0;
    uint count = uint(min(density, 1.0) * 360.0);
    float angle = 0.0;
    float offset = 1.0 / float(count) * (2 * M_PI);
    float intensity = 0.0;
    for (uint i = 0u; i < count; ++i) {
        angle += offset;

        vec2 rect_pos = pos;
        rect_pos = rot(rect_pos, angle);
        rect_pos = trans(rect_pos, vec2(0.0, 1.5));
        float sdf = rectangle(rect_pos, half_size);
        intensity += 1.0 - smoothstep(-softness, softness, sdf);
    }

    return 1.0 - clamp(intensity * strength, 0.0, 1.0);
}


float scratches(
    vec2 position,
    vec2 size,
    float strength,
    float density,
    float length,
    float width,
    float rotation,
    float rotation_variation,
    float softness,
    vec2 parallax

) {
    vec2 pos = position;
    pos = scale(pos, size);
    pos = rot(pos, rotation);
    vec2 rotated_parallax = rot(parallax, rotation);

    vec2 half_size = vec2(width, length) / 2.0;
    float rot_var = rotation_variation * M_PI;

    float intensity = 0.0;
    uint count = uint(min(density, 1.0) * 1000.0);
    for (uint i = 0u; i < count; i++) {
        vec2 center;
        center.x = noise(vec2(i, 0.0));
        center.y = noise(vec2(i, 1.0));
        center += rotated_parallax;
        center = wrap(center, 1) * 2.0 - 1.0;

        float angle = (noise(vec3(i, count, 2.0)) - 0.5f) * rot_var;
        vec2 rect_pos = pos;
        rect_pos = rot(rect_pos, angle);
        rect_pos = trans(rect_pos, center);
        float sdf = rectangle(rect_pos, half_size);
        intensity += 1.0 - smoothstep(-softness, softness, sdf);
    }

    return 1.0 - clamp(intensity * strength, 0.0, 1.0);
}

float dust(
    vec2 position,
    vec2 size,
    float strength,
    float density,
    float radius,
    float softness,
    vec2 parallax
) {
    vec2 pos = position;
    pos = scale(pos, size);
    float intensity = 0.0;
    uint count = uint(min(density, 1.0) * 1000.0);
    for (uint i = 0u; i < count; i++) {
        vec2 center;
        center.x = noise(vec2(i, 0.0));
        center.y = noise(vec2(i, 1.0));
        center += parallax;
        center = wrap(center, 1) * 2.0 - 1.0;

        vec2 circle_pos = trans(pos, center);
        float sdf = circle(circle_pos, radius);
        intensity += 1.0 - smoothstep(-softness, softness, sdf);
    }

    return 1.0 - clamp(intensity * strength, 0.0, 1.0);
}

float image(
    vec2 position,
    vec2 size,
    float strength,
    float black,
    float white,
    sampler2D tex
) {
    vec2 pos = position;
    pos = scale(pos, size);

    vec2 uv = pos / 2.0 + 0.5f;
    float mask = texture(tex, uv).x;

    // Apply black and white point
    if (mask < black) {
        mask = 0.0;
    }
    if (mask > white) {
        mask = 1.0;
    }

    float intensity = 1.0 - (strength * (1.0 - mask));

    return intensity;
}


float aperture(vec2 pos) {
    float intensity = shape(
        pos,
        shape_size,
        shape_blades,
        shape_roundness,
        shape_rotation,
        shape_softness
    );

    if (grating_strength > 0.0) {
        float mask = grating(
            pos,
            shape_size,
            grating_strength,
            grating_density,
            grating_length,
            grating_width,
            grating_softness
        );
        intensity *= mask;
    }

    if (scratches_strength > 0.0) {
        float mask = scratches(
            pos,
            shape_size,
            scratches_strength,
            scratches_density,
            scratches_length,
            scratches_width,
            scratches_rotation,
            scratches_rotation_variation,
            scratches_softness,
            scratches_parallax
        );
        intensity *= mask;
    }

    if (dust_strength > 0.0) {
        float mask = dust(
            pos,
            shape_size,
            dust_strength,
            dust_density,
            dust_radius,
            dust_softness,
            dust_parallax
        );
        intensity *= mask;
    }

    if (image_strength > 0.0) {
        float mask = image(
            pos,
            image_size,
            image_strength,
            image_black,
            image_white,
            image_texture
        );
        intensity *= mask;
    }
    return intensity;
}

void main() {
    vec2 p = gl_FragCoord.xy;
    vec2 pos = convert_ndc(p, resolution);

    uint samples = 8u;
    float intensity = 0.0;
    vec2 offset = vec2(-0.5, -0.5);
    float delta = 1.0 / samples;

    for (uint y = 0u; y < samples; ++y) {
        offset.x = -0.5;
        for (uint x = 0u; x < samples; ++x) {
            vec2 uv = convert_ndc(p + offset, resolution);
            intensity += aperture(uv);
            offset.x += delta;
        }
        offset.y += delta;
    }
    intensity /= samples * samples;

    rgba = vec4(intensity);
}
