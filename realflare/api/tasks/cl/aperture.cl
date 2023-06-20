float2 wrap(float2 value, float m) {
	return fmod(m + fmod(value, m), m);
}

__kernel void aperture_shape(
	write_only image2d_t image,
	const float2 size,
	const int blades,
	const float rotation,
	const float roundness,
	const float softness
	)
{
	int2 p;
	p.x = get_global_id(0);
	p.y = get_global_id(1);
	int2 dims = get_image_dim(image);

	float2 ndc = convert_ndc(p, dims);
	float2 pos = ndc;
	pos = scale(pos, size);
	pos = rot(pos, rotation);

	// blades
	float sdf = 0.0f;
	for(int i = 0; i < blades; ++i) {
		float angle = ((float) i / blades + 0.25f) * 2 * M_PI_F;
		float2 axis = (float2)(cos(angle), sin(angle));
		sdf = max(sdf, dot(axis, pos));
	}

	// roundness
	// match start position bottom: (-pos.x, -pos.y)
	// fit into 0 - 1: + 0.5f
	float circular_gradient = atan2(-pos.x, -pos.y) / (2 * M_PI_F) + 0.5f;
	// center sine: + 0.5f
	float blades_gradient = fmod(circular_gradient * blades + 0.5f, 1);
	float roundness_gradient = sin(blades_gradient * M_PI_F);

	sdf += roundness_gradient * roundness;

	// intensity
	float intensity = 1 - smoothstep(1 - softness, 1 + softness, sdf);
	intensity = intensity;

	write_imagef(image, p, intensity);
}


__kernel void aperture_grating(
	read_write image2d_t image,
	const float2 size,
	const float strength,
	const float density,
	const float length,
	const float width,
	const float softness
	)
{
	int2 p;
	p.x = get_global_id(0);
	p.y = get_global_id(1);
	int2 dims = get_image_dim(image);

	float2 ndc = convert_ndc(p, dims);
	float2 pos = scale(ndc, size);

	float intensity = read_imagef(image, p).x;

	float2 half_size = (float2) (width, length * 2) / 2;
	float sdf = 1;
	int count = fmin(density, 1) * 360;
	float angle = 0;
	float offset = 1.0f / count * (2 * M_PI_F);
	for (int i = 0; i < count; i++) {
		angle += offset;

	 	float2 rect_pos = pos;
	 	rect_pos = rot(rect_pos, angle);
	 	rect_pos = trans(rect_pos, (float2) (0, 1.5f));
	    sdf = min(sdf, rectangle(rect_pos, half_size));
	}
	intensity *=  1 - (strength * smoothstep(softness, -softness, sdf));

	write_imagef(image, p, intensity);
}

__kernel void aperture_scratches(
	read_write image2d_t image,
	const float2 size,
	const float strength,
	const float density,
	const float length,
	const float rotation,
	const float rotation_variation,
	const float width,
	const float2 parallax,
	const float softness
	)
{
	int2 p;
	p.x = get_global_id(0);
	p.y = get_global_id(1);
	int2 dims = get_image_dim(image);

	float2 ndc = convert_ndc(p, dims);
	float2 pos = ndc;
	pos = scale(pos, size);
	pos = rot(pos, rotation);

	float intensity = read_imagef(image, p).x;


	float2 half_size = (float2) (width, length) / 2;

	float rot_var = rotation_variation * M_PI_F;

	float sdf = 1;
	int count = fmin(density, 1) * 1000;
	for (int i = 0; i < count; i++) {
		float2 center;
		center.x = noise(i, count, 0);
		center.y = noise(i, count, 1);
		center += parallax;
		center = wrap(center, 1) * 2 - 1;

		float angle = (noise(i, count, 2) - 0.5f) * rot_var;
	 	float2 rect_pos = pos;
	 	rect_pos = rot(rect_pos, angle);
	 	rect_pos = trans(rect_pos, center);
	    sdf = min(sdf, rectangle(rect_pos, half_size));
	}
	intensity *=  1 - (strength * smoothstep(softness, -softness, sdf));

	write_imagef(image, p, intensity);
}


__kernel void aperture_dust(
	read_write image2d_t image,
	const float2 size,
	const float strength,
	const float density,
	const float radius,
	const float2 parallax,
	const float softness
	)
{
	int2 p;
	p.x = get_global_id(0);
	p.y = get_global_id(1);
	int2 dims = get_image_dim(image);

	float2 ndc = convert_ndc(p, dims);
	float2 pos = scale(ndc, size);

	float intensity = read_imagef(image, p).x;

	float sdf = 1;
	int count = fmin(density, 1) * 1000;
	for (int i = 0; i < count; i++) {
		float2 center;
		center.x = noise(i, count, 0);
		center.y = noise(i, count, 1);
		center += parallax;
		center = wrap(center, 1) * 2 - 1;

	 	float2 circle_pos = trans(pos, center);
	    sdf = min(sdf, circle(circle_pos, radius));
	}
	intensity *=  1.0f - (strength * smoothstep(softness, -softness, sdf));

	write_imagef(image, p, intensity);
}


__kernel void aperture_image(
	read_write image2d_t image,
	const float2 size,
	const float strength,
	read_only image2d_t texture,
	const float2 texture_size
	)
{
	int2 p;
	p.x = get_global_id(0);
	p.y = get_global_id(1);
	int2 dims = get_image_dim(image);

	// float2 uv = convert_uv(p, dims);
	float2 ndc = convert_ndc(p, dims);
	float2 pos = scale(ndc, size * texture_size);

	float2 uv = pos / 2 + 0.5f;

	float intensity = read_imagef(image, p).x;

	sampler_t sampler = CLK_NORMALIZED_COORDS_TRUE | CLK_ADDRESS_REPEAT | CLK_FILTER_LINEAR;
	float mask_ = read_imagef(texture, sampler, uv).x;

	intensity *=  1.0f - (strength * (1.0f - mask_));

	write_imagef(image, p, intensity);
}
