static float noise(float x, float y, float z) {
    float ptr = 0.0f;
    return fract(sin(x * 112.9898f + y * 179.233f + z * 237.212f) * 43758.5453f, &ptr);
}

__kernel void sample_simple(
    write_only image2d_t image,
    read_only image2d_t fourier_spectrum,
    read_only image2d_t light_spectrum,
    const int samples,
    const float blur,
    const float rotation,
    const float rotation_weight,
    const float2 fadeout,
    const float intensity
)
{
    int px = get_global_id(0);
    int py = get_global_id(1);

    int2 dims = get_image_dim(image);

	sampler_t sampler = CLK_NORMALIZED_COORDS_TRUE | CLK_ADDRESS_CLAMP | CLK_FILTER_LINEAR;

	float3 rgb = (float3)(0, 0, 0);

	for (int t = 0; t < samples; ++t)
	{
		// https://people.mpi-inf.mpg.de/~ritschel/Papers/TemporalGlare.pdf
		// [Ritschel et al. 2009] 5. Implementation > Chromatic Blur
		// Take a sample from all visible wavelengths
		float step = (float) t / samples;
    	float wavelength = (float) LAMBDA_MIN + step * (LAMBDA_MAX - LAMBDA_MIN);

    	float seed = t * 4;

		// dx, dy are coordinates in uv space with a randomized blur offset
		float dx = (float)(px + blur * (noise((float) px, (float) py, seed) - 0.5f)) / dims.x;
		float dy = (float)(py + blur * (noise((float) px, (float) py, seed + 1) - 0.5f)) / dims.y;

		// dx, dy are now in ndc space
		dx -= 0.5f;
		dy -= 0.5f;

		float sx = dx * LAMBDA_MID / wavelength;
		float sy = dy * LAMBDA_MID / wavelength;

		// generate the angle that we rotate the lookup by
		// ringing weights the samples more toward the center or the outside of the rotation
		float sign = (noise((float) px, (float) py, seed + 2) > 0.5f) ? 1.0f : -1.0f;
		float angle = sign * rotation * (1.0f - pow(noise((float) px, (float) py, seed + 3), rotation_weight));

		// standard trigonometric formula to rotate the coordinates around by an angle
		// https://en.wikipedia.org/wiki/Rotation_of_axes
		float rx = sx, ry = sy;
		sx = rx * cos(angle) + ry * sin(angle);
		sy = ry * cos(angle) - rx * sin(angle);

		// revert to uv space
		sx += 0.5f;
		sy += 0.5f;

		// sample the intensity from the fourier power spectrum
		// sampling happens in normalized space
		float fourier_intensity = read_imagef(fourier_spectrum, sampler, (float2)(sx, sy)).x;
		// sample XYZ color data from light spectrum
		float3 xyz = read_imagef(light_spectrum, sampler, (float2)(step, 0)).xyz;
		rgb += xyz * fourier_intensity;
	}
	rgb /= samples;

	// ellipse
	float a = (float) dims.x / 2;
	float b = (float) dims.y / 2;
	float x = (float) px - a;
	float y = (float) py - b;
	float radius = (x * x) / (a * a) + (y * y) / (b * b);
	rgb *= smoothstep(fadeout.y, fadeout.x, radius);
	rgb *= intensity;

	float4 output = xyz_to_ap1((float4)(rgb, 1));
    write_imagef(image, (int2)(px, py), output);
}
