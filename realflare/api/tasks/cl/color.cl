// https://github.com/ampas/aces-dev/blob/master/transforms/ctl/README-MATRIX.md

float4 xyz_to_ap1(const float4 rgba)
{
	float4 output = 0;
	output.x =  1.6410233797 * rgba.x + -0.3248032942 * rgba.y + -0.2364246952 * rgba.z;
	output.y = -0.6636628587 * rgba.x +  1.6153315917 * rgba.y +  0.0167563477 * rgba.z;
	output.z =  0.0117218943 * rgba.x + -0.0082844420 * rgba.y +  0.9883948585 * rgba.z;
	return output;
}
