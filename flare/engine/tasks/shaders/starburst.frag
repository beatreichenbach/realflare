#version 430 core

#define M_PI 3.14159265359f
#define LAMBDA_MIN 390u
#define LAMBDA_MID 560u
#define LAMBDA_MAX 730u

uniform Params {
    vec2 resolution;
    vec2 position;
    float blur;
    float rotation;
    float rotation_weight;
    float intensity;
    float vignetting;
    float fft_width;
    uint samples;
    uint _pad;
};

uniform sampler2D fft_image;
uniform sampler2D spectral_image;

out vec4 rgba;

float smooth_vignette(vec2 uv) {
    float r = length(uv * 2.0 - 1.0);
    return 1.0 - smoothstep(0.8, 1.0, r);
}

// Return a spectral psf sampled from an fft by taking samples from all wavelengths.
// See "Temporal Glare: Real-Time Dynamic Simulation of the Scattering in the Human Eye"
// Chapter 5.
vec4 spectral(
    vec2 ndc,
    float blur,
    float rotation,
    float rotation_weight,
    uint samples
) {
    vec4 color;

    uint lambda_delta = LAMBDA_MAX - LAMBDA_MIN;
    for (uint t = 0u; t < samples; ++t) {
        float step = float(t) / samples;
        float seed = float(t) * 4.0;
        float wavelength = step * lambda_delta + LAMBDA_MIN;
        vec2 pos = ndc;
        vec4 rand = vec4(
            noise(vec3(ndc, seed)),
            noise(vec3(ndc, seed + 1.0)),
            noise(vec3(ndc, seed + 2.0)),
            noise(vec3(ndc, seed + 3.0))
        );

        // Blur
        float radius = blur * sqrt(rand.x);
        float alpha = rand.y * 2.0 * M_PI;
        pos.x += cos(alpha) * radius;
        pos.y += sin(alpha) * radius;

        // Chroma
        pos = scale(pos, vec2(wavelength / LAMBDA_MID));

        // Rotation
        // The rotation_weight biases semples to the center or outside of the rotation.
        float sign = (rand.z > 0.5) ? 1.0 : -1.0;
        float bias = 1.0 - pow(rand.w, rotation_weight);
        float angle = sign * rotation * bias;
        pos = rot(pos, angle);

        // Sample the intensity from the fourier power spectrum
        vec2 uv = pos * 0.5 + 0.5;
        if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
            continue;
        }
        float fourier_intensity = texture(fft_image, uv).x;
        fourier_intensity *= 1 - vignetting + smooth_vignette(uv) * vignetting;

        // Sample XYZ color data from the light spectrum
        vec4 xyz = texture(spectral_image, vec2(step, 0));
        color += xyz * fourier_intensity;
    }

    color /= samples;

    return color;
}

void main() {
    vec2 p = gl_FragCoord.xy;
    vec2 ndc = convert_ndc(p, resolution);
    ndc -= position;
    ndc *= resolution / fft_width;

    rgba = spectral(ndc, blur, rotation, rotation_weight, samples);
    rgba *= intensity;
}