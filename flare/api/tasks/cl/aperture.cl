float frac(
	float v
	)
{
	return v - floor(v);
}


float fade_aperture_edge(
	float radius,
	float fade,
	float signed_distance
	)
{
	float l = radius;
	float u = radius + fade;
	float s = u - l;
	float c = 1.f - clamp(clamp(signed_distance - l, 0.0f, 1.0f) / s, 0.0f, 1.0f);
	return smoothstep(0.0f, 1.0f, c);
}

float smax(
	float a,
	float b,
	float k
	)
{
	float diff = a - b;
	float h = clamp(0.5f + 0.5f * diff / k, 0.0f, 1.0f);
	return b + h * (diff + k * (1.0f - h));
}

float fit(
	const float x,
	const float old_min,
	const float old_max,
	const float new_min,
	const float new_max
	)
{
	return (new_max - new_min) * (x - old_min) / (old_max - old_min) + new_min;
}

__kernel void aperture(
	write_only image2d_t buffer,
	const int blades_count,
	const float softness,
	const float fstop
)
{
	int x = get_global_id(0);
	int y = get_global_id(1);
	int2 dims = get_image_dim(buffer);

	float2 ndc;
	ndc.x = (float) (x) / (dims.x - 1) - 0.5f;
	ndc.y = (float) (y) / (dims.y - 1) - 0.5f;
	ndc *= 2.0f;

	float4 rgba = {0.0f, 0.0f, 0.0f, 0.0f};

	float width = fit(fstop, 1.0f, 32.0f, 1.0f, 0.01f);

	float radius = 0.02f;
	float rotation = 4.0f;
	float aperture_fft;

	float a = (atan2(ndc.x, ndc.y) + rotation) / (M_PI_F * 2) + 3.0f / 4.0f;
	float o = frac(a * blades_count + 0.5);
	float name_this_var = clamp((blades_count - 4) / 10.f, 0.0f, 1.0f);
	float w1 = mix(0.010f, 0.001f, name_this_var);
	float w2 = mix(0.025f, 0.001f, name_this_var);
	float s0 = sin(o * 2 * M_PI_F);
	float s1 = s0 * w1;
	float s2 = s0 * w2;

	// fft aperture shape
	float signed_distance = 0.f;
	for(int i = 0; i < blades_count; ++i) {
		float angle = rotation  + (i / (float)(blades_count)) * (M_PI_F * 2);
		float2 axis = (float2)(cos(angle), sin(angle));
		signed_distance = max(signed_distance, dot(axis, ndc));
	}

	// add wavey pattern
	// signed_distance += s1;

	// hard corner aperture
	aperture_fft = fade_aperture_edge(width, softness, signed_distance);

	// rounding corners
	signed_distance = 0.0f;
	for(int i = 0; i < blades_count; ++i) {
		float angle = rotation + (i / (float)(blades_count)) * (M_PI_F * 2);
		float2 axis = (float2)(cos(angle), sin(angle));
		signed_distance = smax(signed_distance, dot(axis, ndc), radius);
	}

	// add wavey pattern
	// signed_distance += s2;
	// round corner aperture
	aperture_fft = fade_aperture_edge(width, softness, signed_distance);

	// Diffraction rings
	{
		float w = 0.2f;
		float s = signed_distance + 0.05f;
		float n = clamp(clamp(s + w, 0.0f, 1.0f) - (1.0f - w), 0.0f, 1.0f);

		float x = n / w;
		float a = x;
		float b = -x + 1.0f;
		float c = min(a, b) * 2.0f;
		float t = (sin(x * 6.0f * M_PI_F - 1.5f) + 1.f) * 0.5f;
		float rings = pow(t * c, 1.0f);
		// aperture_fft = (aperture_fft + rings * 0.125f) / 1.125f;
	}

	rgba += (float4) (aperture_fft, aperture_fft, aperture_fft, 0);

	write_imagef(buffer, (int2)(x, y), aperture_fft);
}
