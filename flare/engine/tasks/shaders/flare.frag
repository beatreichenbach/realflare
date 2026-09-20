#version 430 core

#define M_PI 3.14159265359f

uniform Params {
    uint wavelength_count;
    uint wavelength_sub_count;
    vec2 screen_scale;
    float ghost_scale;
    float intensity;
    float _pad[2];
};

in VertexData {
    float rrel;
    float reflectance;
    float intensity;
    float wavelength_pos;
    vec2 uv;
} v_in;

uniform sampler2D spectral_image;
uniform sampler2D ghost_image;

out vec4 rgba;

void main() {
    vec2 p = gl_FragCoord.xy;

    float rrel_intensity = smoothstep(1.0f, 0.95f, v_in.rrel);
    float ghost_intensity = texture(ghost_image, v_in.uv).x;
    float area_intensity = max(v_in.intensity, 0.0f);
    float coating_intensity = max(v_in.reflectance, 0.0f);

    float total = rrel_intensity * ghost_intensity * area_intensity * coating_intensity * intensity;
    uint total_wavelength_count = wavelength_count * wavelength_sub_count;
    total_wavelength_count -= wavelength_sub_count > 1u ? 1u : 0u;
    total /= total_wavelength_count;

    rgba = vec4(total);
    if(v_in.wavelength_pos >= 0.0f) {
        rgba *= texture(spectral_image, vec2(v_in.wavelength_pos, 0.0f));
    }
}
