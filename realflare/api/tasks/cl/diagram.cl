bool is_line(
	const float2 pos,
	const float2 point0,
	const float2 point1,
	const float width
	)
{
	// check if pixel is inside line
	float2 v = point1 - point0;
	float2 a = pos - point0;
	float2 b = pos - point1;

	bool between = dot(v, a) > 0 && dot(v, b) < 0;
	float d = fabs(v.x*a.y - a.x*v.y) / length(v);
	bool close = (d <= width / 2);

	return (between && close);

}

__kernel void lenses(
	write_only image2d_t buffer,
	__constant LensElement *lens_elements,
	const int lenses_count,
	const int aperture_index,
	const float scale
)
{
	int px = get_global_id(0);
	int py = get_global_id(1);
	int2 dims = get_image_dim(buffer);

	float x = (float) px;
	float y = (float) (dims.y / 2 - py);

	float4 rgba = (float4) (0, 0, 0, 0);
	if((int) y == 0) {
		rgba.x = 1;
	}

	for (size_t i = 0; i < lenses_count; ++i)
	{
		float r = lens_elements[i].radius * scale;
		float h = lens_elements[i].height * scale;
		float c = lens_elements[i].center * scale;

		if (r == 0 && fabs(y) < h && (int) x == (int) c) {
			if (i == aperture_index || i == lenses_count - 1 ) {
				// color aperture lens and sensor green
				rgba.y = 1;
			} else {
				rgba.z = 1;
			}
			// early termination
			break;
		}
		else {
			float r_circle = sqrt(pow(x - c, 2) + pow(y, 2));
			// only draw the half we want
			bool draw_half = (r > 0) ? (x < c) : (x > c);

			if(draw_half && (int) fabs(r) == (int) r_circle && fabs(y) < h) {
				rgba.z = 1;
			}
		}
	}
	write_imagef(buffer, (int2)(px, py), rgba);
}


__kernel void intersections (
	read_write image2d_t image,
	__global Intersection *intersections,
	const int intersections_count,
	const int ray_count,
	const float scale
	)
{
	int px = get_global_id(0);
	int py = get_global_id(1);

	int2 dims = get_image_dim(image);
	float2 pos = (float2) (px, dims.y / 2 - py);

	float thickness = 1.0f;
	float normal_length = 1.0f;

    // shape = path, grid, grid, wavelength, intersections

	int path_id = 0;
	int wavelength_id = 0;
	int wavelength_count = 1;

	float4 rgba = read_imagef(image, (int2) (px, py));

	for (size_t ray_id = 0; ray_id < ray_count; ray_id++) {
		int ray_index = ((path_id * ray_count + ray_id) * wavelength_count + wavelength_id);

		for (size_t inter_id = 0; inter_id < intersections_count; inter_id++) {
			int inter_index = ray_index * intersections_count + inter_id;
			Intersection inter1 = intersections[inter_index];
			Intersection inter2 = intersections[inter_index + 1];
			if (!inter2.hit) {
				break;
			}

			float2 point0 = inter1.pos.zy * scale;
			point0 *= -1;
			if (inter_id == intersections_count) {
				break;
			}
			float2 point1 = inter2.pos.zy * scale;
			point1 *= -1;


			// draw normal
			float2 normal = inter1.normal.zy * scale;
			float2 point_normal = point0 - normal * normal_length;
			if(is_line(pos, point0, point_normal, thickness)) {
				rgba = (float4) (0.25, 0, 0, 0);
			}

			if (point1.x == 0) {
				break;
			}

			// draw ray
			float value = (float) (ray_id + 1) / ray_count;
			value = inter1.incident;
			value = 0.25f;
			if(is_line(pos, point0, point1, thickness)) {
				rgba += (float4) (value, value, value, 0);
			}

		}
	}
	write_imagef(image, (int2)(px, py), rgba);
}
