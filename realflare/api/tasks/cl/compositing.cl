__kernel void composite(
	__read_only image2d_t image,
	__write_only image2d_t output,
	__read_only image2d_t starburst,
	float2 light_position,
	float2 scale
)
{
	// TODO: can be optimized by only processing the pixels where starburst is overlapping
	int x = get_global_id(0);
	int y = get_global_id(1);

	int2 image_dims = get_image_dim(image);
	int2 starburst_dims = get_image_dim(starburst);

	float2 pos = (float2)(x, y);
	float2 center_pos = (light_position / 2 * (float2) (1, -1) + 0.5f) * convert_float2(image_dims);
	float2 half_dims = convert_float2(starburst_dims) * scale / 2;

	float2 starburst_pos = pos - (center_pos - half_dims);
	starburst_pos /= convert_float2(starburst_dims) * scale;

	float4 rgba = read_imagef(image, (int2)(x, y));

	sampler_t sampler = CLK_FILTER_LINEAR | CLK_NORMALIZED_COORDS_TRUE | CLK_ADDRESS_CLAMP;
	rgba += read_imagef(starburst, sampler, starburst_pos);

	write_imagef(output, (int2)(x, y), rgba);
}
