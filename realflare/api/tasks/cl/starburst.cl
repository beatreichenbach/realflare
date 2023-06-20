__kernel void starburst(
    write_only image2d_t image,
    read_only image2d_t fourier_spectrum,
    read_only image2d_t light_spectrum,
    const int samples,
    const float blur,
    const float rotation,
    const float rotation_weight,
    const float2 vignetting,
    const float intensity
)
{

    int2 dims = get_image_dim(image);
    int2 p;
    p.x = get_global_id(0);
    p.y = get_global_id(1);

	// dx, dy are coordinates in uv space with a randomized blur offset
	float2 ndc = convert_ndc(p, dims);




	// float2 size = convert_float2(starburst_dims) / convert_float2(dims);
	float2 offset = (float2) (0.5f, -0.5f);

	// transform
	ndc = trans(ndc, offset);
	// ndc = scale(ndc, size);



	sampler_t sampler = CLK_NORMALIZED_COORDS_TRUE | CLK_ADDRESS_CLAMP | CLK_FILTER_LINEAR;
	const int lambda_delta = LAMBDA_MAX - LAMBDA_MIN;

	float4 rgba = 0;
	for (int t = 0; t < samples; ++t)
	{
		// https://people.mpi-inf.mpg.de/~ritschel/Papers/TemporalGlare.pdf
		// [Ritschel et al. 2009] 5. Implementation > Chromatic Blur
		// Take a sample from all visible wavelengths

		float step = (float) t / samples;
		float wavelength = step * lambda_delta + LAMBDA_MIN;
    	float seed = t * 4;
    	float2 pos = ndc;

    	// blur
    	float radius = blur * sqrt(noise(p.x, p.y, seed));
    	float alpha = noise(p.x, p.y, seed + 1) * 2 * M_PI_F;
    	pos.x += cos(alpha) * radius;
    	pos.y += sin(alpha) * radius;

    	// chroma
    	pos = scale(pos, 1 - (1 - (wavelength / LAMBDA_MID)) * 1.0f);

    	// rotation
		// weight creates more samples more toward the center or the outside of the rotation
		float sign = (noise(p.x, p.y, seed + 2) > 0.5f) ? 1.0f : -1.0f;
		float angle = sign * rotation * (1.0f - pow(noise(p.x, p.y, seed + 3), rotation_weight));
		pos = rot(pos, angle);

		// uv space
		float2 uv =  pos * 0.5f + 0.5f;

		// sample the intensity from the fourier power spectrum
		float fourier_intensity = read_imagef(fourier_spectrum, sampler, uv).x;

		// sample XYZ color data from light spectrum
		float4 xyz = read_imagef(light_spectrum, sampler, (float2)(step, 0));
		// xyz *= xyz.x + xyz.y + xyz.z;
		rgba += xyz * fourier_intensity;

	}


	// samples
	rgba /= samples;

	// vignetting
	if (!isnan(vignetting.x)) {
		float sdf = circle(ndc, 0);
		rgba *= smoothstep(vignetting.y, vignetting.x, sdf);
	}

	// intensity
	rgba *= intensity;

	float4 output = xyz_to_ap1(rgba);
    write_imagef(image, p, output);
}
