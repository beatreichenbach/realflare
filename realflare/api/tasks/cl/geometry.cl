float2 convert_uv(
	const int2 p,
	const int2 dims
	)
{
	return convert_float2(p) / convert_float2(dims - 1);
}

float2 convert_ndc(
	const int2 p,
	const int2 dims
	)
{
	return 2.0f * convert_uv(p, dims) - 1.0f;
}

float2 trans(float2 pos, float2 offset){
    return pos - offset;
}

// standard trigonometric formula to rotate the coordinates around by an angle
// https://en.wikipedia.org/wiki/Rotation_of_axes
float2 rot(float2 pos, float angle){
    float s = sin(angle);
    float c = cos(angle);
    return (float2) (pos.x * c + pos.y * s, pos.y * c - pos.x * s);
}

float2 scale(float2 pos, float2 scale) {
	return pos / fmax(scale, FLT_MIN);
}


float circle(float2 pos, float radius){
    return length(pos) - radius;
}

float rectangle(float2 pos, float2 half_size){
    float2 edge_distance = fabs(pos) - half_size;
    float outside = length(fmax(edge_distance, 0.0f));
    float inside = fmin(fmax(edge_distance.x, edge_distance.y), 0.0f);
    return outside + inside;
}

