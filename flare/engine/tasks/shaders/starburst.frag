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
    float fft_radius;
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

    vec2 p = gl_FragCoord.xy;
    float fft_resolution = float(textureSize(fft_image, 0).x);

    for (uint t = 0u; t < samples; ++t) {
        float step = (float(t) + 0.5) / samples;
        float wavelength = step * lambda_delta + LAMBDA_MIN;
        vec2 pos = ndc;

        uint seed = pcg_hash(uint(p.x) + 0x9E3779B9u * pcg_hash(uint(p.y) + 0x85EBCA6Bu * (t + 1u)));
        vec4 rand = vec4(
            random(seed),
            random(seed + 1u),
            random(seed + 2u),
            random(seed + 3u)
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

        // Prefilter the fft with a mip level matching the pixel footprint.
        // The scaling maps one pixel to the texel size in uv space,
        // which spans that many fft texels.
        float texel_size = (wavelength / float(LAMBDA_MID)) / (length(resolution) * fft_radius);
        float texel_footprint = fft_resolution * texel_size;
        float lod = max(log2(texel_footprint), 0.0);

        float fourier_intensity = textureLod(fft_image, uv, lod).x;

        // Vignette to hide artefacts
        fourier_intensity *= 1 - vignetting + smooth_vignette(uv) * vignetting;

        // Sample spectral color data from the light spectrum (in render space)
        vec4 xyz = texture(spectral_image, vec2(step, 0));
        // Long wavelengths spread over a wider area, so dim each sample by the
        // square of its wavelength ratio to keep the energy per wavelength equal.
        float falloff = pow(float(LAMBDA_MID) / wavelength, 2.0);
        color += xyz * fourier_intensity * falloff;
    }

    color /= samples;

    return color;
}

void main() {
    vec2 p = gl_FragCoord.xy;
    vec2 ndc = convert_ndc(p, resolution);
    ndc -= position;
    ndc *= resolution / (length(resolution) * fft_radius);

    rgba = spectral(ndc, blur, rotation, rotation_weight, samples);
    rgba *= intensity;
}