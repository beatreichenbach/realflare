__kernel void composite(
	write_only image2d_t composite,
	read_only image2d_t flare,
	read_only image2d_t starburst,
	const float2 position
)
{
	sampler_t sampler = CLK_NORMALIZED_COORDS_TRUE | CLK_ADDRESS_CLAMP  | CLK_FILTER_LINEAR;

	int2 p;
	p.x = get_global_id(0);
	p.y = get_global_id(1);
	int2 dims = get_image_dim(composite);
	int2 starburst_dims = get_image_dim(starburst);

	float2 ndc = convert_ndc(p, dims);
	float2 size = convert_float2(starburst_dims) / convert_float2(dims);
	float2 offset = (float2) (position.x, -position.y);


	// transform
	ndc = trans(ndc, offset);
	ndc = scale(ndc, size);
	float2 uv = ndc * 0.5f + 0.5f;

	// read
	float4 rgba = read_imagef(flare, p);
	float4 starburst_rgba = read_imagef(starburst, sampler, uv);
	rgba += starburst_rgba;

	write_imagef(composite, p, rgba);
}
