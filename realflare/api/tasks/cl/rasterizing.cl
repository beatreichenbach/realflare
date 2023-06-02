// leave room for 1 bit batch header to store whether list is empty
#define BATCH_PRIMITIVE_COUNT 255

int edge_function_int(
	int2 a,
	int2 b,
	int2 c
	)
{
	// TODO: edge function can be optimized, see advanced section in link
	//  https://www.scratchapixel.com/lessons/3d-basic-rendering/rasterization-practical-implementation/rasterization-stage
	// https://fgiesen.wordpress.com/2013/02/08/triangle-rasterization-in-practice/
	return (a.x - b.x) * (c.y - a.y) - (a.y - b.y) * (c.x - a.x);
}

float edge_function_float(
	float2 a,
	float2 b,
	float2 c
	)
{
	return (a.x - b.x) * (c.y - a.y) - (a.y - b.y) * (c.x - a.x);
}

bool is_top_left(
	int2 a,
	int2 b
	)
{
	// https://fgiesen.wordpress.com/2013/02/08/triangle-rasterization-in-practice/
	int2 edge = b - a;
	return ((edge.y == 0 && edge.x > 0) || edge.y > 0);
}

bool intersect_tri(
	int2 p,
	int2 p0,
	int2 p1,
	int2 p2
	)
{
	// don't render common edges twice, top-left rule
	int bias01 = is_top_left(p0, p1) ? 0 : -1;
	int bias12 = is_top_left(p1, p2) ? 0 : -1;
	int bias20 = is_top_left(p2, p0) ? 0 : -1;

	int l01 = edge_function_int(p0, p1, p) + bias01;
	int l12 = edge_function_int(p1, p2, p) + bias12;
	int l20 = edge_function_int(p2, p0, p) + bias20;

	bool front = (l01 >= 0 && l12 >= 0 && l20 >= 0);
	bool back = (l01 < 0 && l12 < 0 && l20 < 0);

	return front;
	return front || back;
}

bool intersect_quad(
	int2 p,
	int2 p0,
	int2 p1,
	int2 p2,
	int2 p3
	)
{
	// don't render common edges twice, top-left rule
	int bias01 = is_top_left(p0, p1) ? 0 : -1;
	int bias12 = is_top_left(p1, p2) ? 0 : -1;
	int bias23 = is_top_left(p2, p3) ? 0 : -1;
	int bias30 = is_top_left(p3, p0) ? 0 : -1;
	int bias20 = is_top_left(p2, p0) ? 0 : -1;

	int l01 = edge_function_int(p0, p1, p) + bias01;
	int l12 = edge_function_int(p1, p2, p) + bias12;
	int l23 = edge_function_int(p2, p3, p) + bias23;
	int l30 = edge_function_int(p3, p0, p) + bias30;
	int l20 = edge_function_int(p2, p0, p) + bias20;

	bool w01 = l01 >= 0;
	bool w12 = l12 >= 0;
	bool w23 = l23 >= 0;
	bool w30 = l30 >= 0;

	// dealing with 3 points in one line
	if (edge_function_int(p0, p1, p2) == 0 && edge_function_int(p0, p2, p3) == 0) return false;
	bool w20 = l20 >= 0;

	// [Hormann Tarini, 2004] 4.1
	bool front = (w20 && w01 && w12 && (w23 || w30)) ||
		(!w20 && w23 && w30 && (w01 || w12));

	bool back = (!w20 && !w01 && !w12 && (!w23 || !w30)) ||
		(w20 && !w23 && !w30 && (!w01 || !w12));

	return front || back;
}

float4 compute_barycentric_quad(
	int2 p,
	int2 p0,
	int2 p1,
	int2 p2,
	int2 p3
	)
{
	// https://core.ac.uk/download/pdf/53544051.pdf
	float2 s0 = convert_float2(p0 - p);
	float2 s1 = convert_float2(p1 - p);
	float2 s2 = convert_float2(p2 - p);
	float2 s3 = convert_float2(p3 - p);

	float a0 = s0.x * s1.y - s1.x * s0.y;
	float a1 = s1.x * s2.y - s2.x * s1.y;
	float a2 = s2.x * s3.y - s3.x * s2.y;
	float a3 = s3.x * s0.y - s0.x * s3.y;

	float d0 = dot(s0, s1);
	float d1 = dot(s1, s2);
	float d2 = dot(s2, s3);
	float d3 = dot(s3, s0);

	float r0 = length(s0);
	float r1 = length(s1);
	float r2 = length(s2);
	float r3 = length(s3);

	if (r0 == 0) return (float4) (1, 0, 0, 0);
	if (r1 == 0) return (float4) (0, 1, 0, 0);
	if (r2 == 0) return (float4) (0, 0, 1, 0);
	if (r3 == 0) return (float4) (0, 0, 0, 1);

	if (a0 == 0) a0 = 1e-3;
	if (a1 == 0) a1 = 1e-3;
	if (a2 == 0) a2 = 1e-3;
	if (a3 == 0) a3 = 1e-3;

	float t0 = (r0 * r1 - d0) / a0;
	float t1 = (r1 * r2 - d1) / a1;
	float t2 = (r2 * r3 - d2) / a2;
	float t3 = (r3 * r0 - d3) / a3;

	float w0 = (t3 + t0) / r0;
	float w1 = (t0 + t1) / r1;
	float w2 = (t1 + t2) / r2;
	float w3 = (t2 + t3) / r3;

	float weight_sum = w0 + w1 + w2 + w3;
	float4 weights = {w0, w1, w2, w3};
	weights /= weight_sum;
	return weights;
}

float3 compute_barycentric_tri(
	int2 p,
	int2 p0,
	int2 p1,
	int2 p2
	)
{
	int area = edge_function_int(p0, p1, p2);
	float3 weights;
	weights.x = edge_function_int(p1, p2, p);
	weights.y = edge_function_int(p2, p0, p);
	weights.z = edge_function_int(p0, p1, p);
	weights /= area;
	return weights;
}

float debug_grid_tri(
	int2 p,
	int2 p0,
	int2 p1,
	int2 p2
	)
{
	return (float) (
		(p.x == p0.x && p.y == p0.y) ||
		(p.x == p1.x && p.y == p1.y) ||
		(p.x == p2.x && p.y == p2.y)
		);
}

float debug_grid_quad(
	int2 p,
	int2 p0,
	int2 p1,
	int2 p2,
	int2 p3
	)
{
	return (float) (
		( p.x ==  p0.x &&  p.y ==  p0.y) ||
		( p.x ==  p1.x &&  p.y ==  p1.y) ||
		( p.x ==  p2.x &&  p.y ==  p2.y) ||
		( p.x ==  p3.x &&  p.y ==  p3.y)
		);
}

int4 quad_neighbors(
	int length,
	int x,
	int y
	)
{
    // length is the amount of rows of the vertex grid
    // neighbors are the quad indexes neighboring (x, y)

	int4 neighbors;

    // top
    neighbors.x = (y - 1) * (length - 1) + (x - 1);
    neighbors.y = neighbors.x + 1;

    // bottom
    neighbors.z = y * (length - 1) + (x - 1);
    neighbors.w = neighbors.z + 1;

    return neighbors;
}

int4 quad_vertexes(
	const int grid_count,
	const int quad_id
	)
{
	int row = quad_id / (grid_count - 1);
	int column = quad_id % (grid_count - 1);
	int4 quads;
	quads.x = row * grid_count + column;
	quads.y = quads.x + 1;
	quads.zw = quads.yx + grid_count;
	return quads;
}


__kernel void prim_shader(
	__global float4 *bounds,
	__global float *areas,
	__global Ray *rays,
	const int grid_count,
	const int ray_count,
	const int wavelength_count,
	const float min_area
	)
{
	// computes areas per primitive per wavelength and the bounding boxes per primitive for all wavelengths

	int path_id = get_global_id(0);
	int path_count = get_global_size(0);
	int quad_id = get_global_id(1);
	int quad_count = get_global_size(1);

	int bounds_index = path_id * quad_count + quad_id;
	float4 prim_group_bounds = (float4) (INFINITY, INFINITY, -INFINITY, -INFINITY);
	char invalid_rrel = 0;
	int4 quads = quad_vertexes(grid_count, quad_id);

	for (int wavelength_id = 0; wavelength_id < wavelength_count; wavelength_id++) {
		if (isnan(prim_group_bounds.x)) {
			// if any of the other wavelengths is culled, don't store bounds
			continue;
		}

		int ray_offset = (path_id * wavelength_count + wavelength_id) * ray_count;
		int area_index = (path_id * quad_count + quad_id) * wavelength_count + wavelength_id;

		Ray r[4];
		r[0] = rays[ray_offset + quads.x];
		r[1] = rays[ray_offset + quads.y];
		r[2] = rays[ray_offset + quads.z];
		r[3] = rays[ray_offset + quads.w];

		float2 pos[4];
		int valid_rays = 0;
		for(int i=0; i < 4; i++) {
			if (!isnan(r[i].reflectance)) {
				pos[valid_rays] = r[i].pos.xy;
				valid_rays++;
			}
		}

		float area = 0;
		if (valid_rays == 4) {
			// http://www.math.brown.edu/tbanchof/midpoint/selfquad.html
			float area0 = edge_function_float(pos[0], pos[1], pos[2]);
			float area1 = edge_function_float(pos[0], pos[2], pos[3]);
			area = fabs(area0 + area1) / 2;
		} else if (valid_rays == 3) {
			// extrapolate area to quad
			area = fabs(edge_function_float(pos[0], pos[1], pos[2]));
			// simulate quad to keep code simple
			pos[3] = pos[2];
			r[3] = r[2];
		} else {
			// cull degenerate prims and don't store area
			prim_group_bounds.x = NAN;
			continue;
		}

		// check rrel
		if (r[0].rrel > 1 && r[1].rrel > 1 && r[2].rrel > 1 && r[3].rrel > 1) {
			invalid_rrel++;
		}

		// store area
		// prevent super bright edges with min area
		areas[area_index] = max(area, min_area);

		// store bounds
		float4 prim_bounds;
		prim_bounds.xy = min(min(pos[0], pos[1]), min(pos[2], pos[3]));
		prim_bounds.zw = max(max(pos[0], pos[1]), max(pos[2], pos[3]));
		prim_group_bounds.xy = min(prim_group_bounds.xy, prim_bounds.xy);
		prim_group_bounds.zw = max(prim_group_bounds.zw, prim_bounds.zw);
	}
	if (invalid_rrel == wavelength_count) {
		// cull the primitive where all wavelengths are outside the lens housing.
		prim_group_bounds.x = NAN;
	}
	bounds[bounds_index] = prim_group_bounds;
}

__kernel void vertex_shader(
	__global Vertex *vertexes,
	__global float *areas,
	__global Ray *rays,
	const int grid_count,
	const float area_orig,
	const float screen_transform,
	const int2 resolution
	)
{
	int path_id = get_global_id(0);
	int path_count = get_global_size(0);
	int ray_id = get_global_id(1);
	int ray_count = get_global_size(1);
	int wavelength_id = get_global_id(2);
	int wavelength_count = get_global_size(2);

	int quad_count = (grid_count - 1) * (grid_count - 1);

	int vertex_index = (path_id * ray_count + ray_id) * wavelength_count + wavelength_id;
	int ray_index = (path_id * wavelength_count + wavelength_id) * ray_count + ray_id;

	// get ray
	Ray r = rays[ray_index];

	// vertex
	Vertex v;
	v.reflectance = r.reflectance;

	// ignore rays that didn't make it to the sensor
	if (!isnan(r.reflectance)) {
		// intensity
		int x = ray_id % grid_count;
		int y = ray_id / grid_count;
		// The reason an array is used is to loop through it, a vector can't be looped through
		int neighbors[4];
		vstore4(quad_neighbors(grid_count, x, y), 0, &neighbors[0]);

		float intensity = 0;
		int neighbor_count = 0;
		for(int i = 0; i < 4; ++i) {
			if(neighbors[i] < 0 || neighbors[i] >= quad_count) continue;

			int area_index = (path_id * quad_count + neighbors[i]) * wavelength_count + wavelength_id;
			if (areas[area_index] > 0) {
				intensity += area_orig / areas[area_index];
				++neighbor_count;
			}
		}
		intensity /= max(neighbor_count, 1);
		v.intensity = intensity;

		// position
		float2 pos = r.pos.xy * screen_transform + convert_float2(resolution) / 2;
		v.pos = pos;

		// uv
		v.uv = (r.pos_apt + 1) / 2;

		// rrel
		v.rrel = r.rrel;
	}

	// write vertex
	vertexes[vertex_index] = v;
}

__kernel void binner(
	__global long* bin_queues,
	const uint2 bin_dims,
	const unsigned int bin_count,
	__global float4* bounds_buffer,
	const unsigned int primitive_count,
	__global int* bin_distribution_counter,
	const float screen_transform,
	const int2 resolution
	)
{
	const unsigned int local_id = get_local_id(0);
	const unsigned int local_size = get_local_size(0);

	const unsigned int batch_index = get_group_id(0);
	const unsigned int batch_count = get_num_groups(0);

	// note: opencl does not require this to be aligned, but certain implementations do
	// correctly align, so async copy will work
	local float4 bounds[BATCH_PRIMITIVE_COUNT] __attribute__((aligned(16)));

	// read input primitive bounds into shared memory (across work-group)
	const unsigned int primitive_id_offset = batch_index * BATCH_PRIMITIVE_COUNT;
	event_t event = async_work_group_copy(
		&bounds[0],
		(global const float4*)&bounds_buffer[primitive_id_offset],
		BATCH_PRIMITIVE_COUNT, 0);
	wait_group_events(1, &event);

	// Use ulong4 vector type to allocate memory, then use pointer queue to store custom bits
	// ulong4 = 8 * 4 * 8 bits = 256 bits = 255 prim bit mask + 1 bit header
	long4 queue;
	uchar* queue_pointer = (uchar*)&queue;

	const unsigned int max_bin_offset = ceil((float) bin_count / local_size);

	// in cases where #bins > #work-items, we need to iterate over all bins (simply offset the bin_index by the #work-items)
	for(unsigned int bin_index_offset = 0; bin_index_offset < max_bin_offset; bin_index_offset++) {
		const unsigned int bin_index = local_id + (bin_index_offset * local_size);
		if(bin_index >= bin_count) break;

		uint2 bin_pos = (uint2)(bin_index % bin_dims.x, bin_index / bin_dims.x);
		int4 bin;
		bin.x = (float) bin_pos.x * BIN_SIZE;
		bin.y = (float) bin_pos.y * BIN_SIZE;
		bin.z = bin.x + BIN_SIZE;
		bin.w = bin.y + BIN_SIZE;

		bool queue_empty = true;

		// init all primitive bytes
		queue = (long4)(0u, 0u, 0u, 0u);

		unsigned int last_primitive_id = min(primitive_id_offset + BATCH_PRIMITIVE_COUNT, primitive_count);
		// iterate over all primitives in this batch
		for(unsigned int primitive_id = primitive_id_offset, primitive_counter = 0u;
			primitive_id < last_primitive_id;
			primitive_id++, primitive_counter++) {

			// prim is degenerate
			if(isnan(bounds[primitive_counter].x)) continue;

			int4 screen_bounds = convert_int4(bounds[primitive_counter] * screen_transform) + (int4) (resolution, resolution) / 2;

			// check if bounds are overlapping bin
			// https://stackoverflow.com/questions/306316/determine-if-two-rectangles-overlap-each-other
			if(screen_bounds.x <= bin.z && screen_bounds.z >= bin.x && screen_bounds.y <= bin.w && screen_bounds.w >= bin.y) {
				const unsigned int queue_bit = (primitive_counter + 1u) % 8u;
				const unsigned int queue_byte = (primitive_counter + 1u) / 8u;
				queue_pointer[queue_byte] |= (1u << queue_bit);
				queue_empty = false;
			}
		}

		// store the "any primitives visible at all" flag in the first bit of the first byte
		queue_pointer[0] |= (queue_empty ? 0u : 1u);

		// copy queue to global memory
		const size_t batch_offset = bin_index * batch_count + batch_index;

		vstore4(queue, batch_offset, bin_queues);
	}
}

float fragment_shader(
	float4 weights,
	Vertex v0,
	Vertex v1,
	Vertex v2,
	Vertex v3,
	__read_only image2d_t ghost
	)
{
	// ghost texture
	float2 uv = weights.x * v0.uv + weights.y * v1.uv + weights.z * v2.uv + weights.w * v3.uv;
	sampler_t sampler_norm = CLK_FILTER_LINEAR | CLK_NORMALIZED_COORDS_TRUE | CLK_ADDRESS_CLAMP_TO_EDGE;
	float ghost_intensity = read_imagef(ghost, sampler_norm, uv).x;

	// relative distance from lens housing, rrel > 1 = ray left lens housing
	float rrel = weights.x * v0.rrel + weights.y * v1.rrel + weights.z * v2.rrel + weights.w * v3.rrel;
	float rrel_intensity = smoothstep(1.0f, 0.95f, rrel);

	// energy preservation
	float area_intensity = weights.x * v0.intensity + weights.y * v1.intensity + weights.z * v2.intensity + weights.w * v3.intensity;

	// anti reflective coating
	float coating_intensity = weights.x * v0.reflectance + weights.y * v1.reflectance + weights.z * v2.reflectance + weights.w * v3.reflectance;

	float intensity;
	area_intensity = max(area_intensity, 0.0f);
	coating_intensity = max(coating_intensity, 0.0f);
	intensity = ghost_intensity * rrel_intensity * area_intensity * coating_intensity;
	// intensity = rrel_intensity * area_intensity * coating_intensity;
	// intensity = area_intensity;
	// intensity =  rrel_intensity;

	return intensity;
}


Vertex mix_vertex(
	Vertex v1,
	Vertex v2,
	const float blend
	)
{
	Vertex v;
	v.pos = mix(v1.pos, v2.pos, blend);
	v.uv = mix(v1.uv, v2.uv, blend);
	v.intensity = mix(v1.intensity, v2.intensity, blend);
	v.rrel = mix(v1.rrel, v2.rrel, blend);
	v.reflectance = mix(v1.reflectance, v2.reflectance, blend);
	return v;
}

__kernel void rasterizer(
	__write_only image2d_t image,
	__read_only image2d_t ghost,
	__read_only image2d_t light_spectrum,
	__global Vertex *vertexes,
	__global long4* bin_queues,
	const int batch_count,
	const int path_count,
	const int wavelength_count,
	const int wavelength_sub_count,
	const int grid_count,
	const int sub_steps,
	__constant uchar *sub_offsets
)
{
	int x = get_global_id(0);
	int y = get_global_id(1);

	int2 dims = get_image_dim(image);

	// write_imagef(image, (int2)(0, 0), (float4) (get_global_size(0), get_global_size(1), 0, 0));
	if (x >= dims.x || y >= dims.y) return;
	int2 p = (int2) (x, y) * sub_steps;
	int2 p_center = p + sub_steps / 2;

	// int round up
	// https://stackoverflow.com/questions/17944/how-to-round-up-the-result-of-integer-division/96921#96921
	int2 bin_dims = (dims + BIN_SIZE - (int2) (1, 1)) / BIN_SIZE;
	int bin_index = (y / BIN_SIZE) * bin_dims.x + (x / BIN_SIZE);
	int quad_count = (grid_count - 1) * (grid_count - 1);
	int vertex_count = grid_count * grid_count;
	int max_wavelength_count = max(wavelength_count - 1, 1);
	int total_samples = wavelength_count * sub_steps * wavelength_sub_count;

	float wavelength_sub_step = 1.0f / wavelength_sub_count;
	float wavelength_step = wavelength_sub_step / wavelength_count;

	// localize bin queues
	// 1 long4 = 256 bytes
	// 256 bytes = 1024 prims (quad_count)
	// local long4 local_bin_queues[BATCH_COUNT];
	// event_t event = async_work_group_copy(
	// 	&local_bin_queues[0],
	// 	(global long4*) &bin_queues[bin_index * batch_count],
	// 	BATCH_COUNT,
	// 	0);
	// wait_group_events(1, &event);

	float4 rgba = (float4) (0, 0, 0, 0);
	sampler_t sampler = CLK_FILTER_LINEAR | CLK_NORMALIZED_COORDS_TRUE | CLK_ADDRESS_CLAMP_TO_EDGE;

	for (int batch_id = 0; batch_id < batch_count; batch_id++) {
		int offset = bin_index * batch_count + batch_id;
		long4 queue = bin_queues[offset];
		// long4 queue = local_bin_queues[batch_id];
		uchar* queue_pointer = (uchar*)&queue;
		// check if first bit is not set (= empty list)
		if ((queue_pointer[0] & 1u) == 0u) continue;

		for (int batch_prim_id = 0; batch_prim_id < BATCH_PRIMITIVE_COUNT; batch_prim_id++) {
			int prim_id = batch_id * BATCH_PRIMITIVE_COUNT + batch_prim_id;
			if (prim_id >= quad_count * path_count) continue;

			const unsigned int queue_bit = (batch_prim_id + 1) % 8u;
			const unsigned int queue_byte = (batch_prim_id + 1) / 8u;
			const bool is_visible = ((queue_pointer[queue_byte] & (1u << queue_bit)) != 0u);
			if (!is_visible) continue;

			int path_id = prim_id / quad_count;
			int quad_id = prim_id % quad_count;

			int4 quads = quad_vertexes(grid_count, quad_id);
			// if (quad_id != 1244) continue;

			int4 vertex_index = (path_id * vertex_count + quads) * wavelength_count;

			Vertex v_source[8];

			v_source[4] = vertexes[vertex_index.x];
			v_source[5] = vertexes[vertex_index.y];
			v_source[6] = vertexes[vertex_index.z];
			v_source[7] = vertexes[vertex_index.w];
			vertex_index++;

			for (int wavelength_id = 0; wavelength_id < max_wavelength_count; wavelength_id++, vertex_index++) {
				v_source[0] = v_source[4];
				v_source[1] = v_source[5];
				v_source[2] = v_source[6];
				v_source[3] = v_source[7];
				v_source[4] = vertexes[vertex_index.x];
				v_source[5] = vertexes[vertex_index.y];
				v_source[6] = vertexes[vertex_index.z];
				v_source[7] = vertexes[vertex_index.w];

				float wavelength_sub_pos = 0;
				float wavelength_pos = ((float) wavelength_id + 0.5f) / wavelength_count;
				for (int i = 0; i < wavelength_sub_count; i++) {
					int2 v_pos[4];
					Vertex v[4];

					for (int j = 0; j < 4; j++) {
						v[j] = mix_vertex(v_source[j], v_source[j + 4], wavelength_sub_pos);
						v_pos[j] = convert_int2(v[j].pos * sub_steps);
					}

					size_t hits = 0;
					for(char s = 0; s < sub_steps; s++) {
						// offset sample position based on n-rook pattern
						int2 sample_pos = p + (int2) (s, sub_offsets[s]);
						if (intersect_quad(sample_pos, v_pos[0], v_pos[1], v_pos[2], v_pos[3])) {
							hits++;
						}
					}
					float intensity = 0;
					if (hits > 0) {
						float4 weights = compute_barycentric_quad(p_center, v_pos[0], v_pos[1], v_pos[2], v_pos[3]);
						intensity += fragment_shader(weights, v[0], v[1], v[2], v[3], ghost) * hits;
					}

					if(wavelength_count > 1) {
						// before optimization:
						// float wavelength_pos = ((float) wavelength_id + 0.5f + wavelength_sub_pos) / wavelength_count;
						float3 xyz = read_imagef(light_spectrum, sampler, (float2) (wavelength_pos, 0)).xyz;
						rgba.xyz += xyz * intensity;
					} else {
						rgba.xyz += intensity;
					}

					wavelength_sub_pos += wavelength_sub_step;
					wavelength_pos += wavelength_step;
				}
			}
		}
	}

	if(rgba.x > 0 || rgba.y > 0 || rgba.z > 0) {
		rgba /= total_samples;
		y = dims.y - (y + 1);
		float4 output = xyz_to_ap1(rgba);
		write_imagef(image, (int2)(x, y), output);
	}
}
