float fresnel_ar(
	float theta0,  // angle of incidence
	float lambda,  // wavelength of ray
	float d1,  // thickness of AR coating
	float n0,  // refractive index of 1st medium
	float n1,  // refractive index of coating layer
	float n2  // refractive index of 2nd medium
){
	// [Ritschel et al. 2009] Supplemental Material - Anti-reflective Coating

	// refraction angles in coating and the 2n dmedium
	float theta1 = asin(sin(theta0) * n0 / n1);
	float theta2 = asin(sin(theta0) * n0 / n2);

	// amplitude for outer refl. / transmission on topmost interface
	float rs01 = -sin(theta0 - theta1) / sin(theta0 + theta1);
	float rp01 = tan(theta0 - theta1) / tan(theta0 + theta1);
	float ts01 = 2 * sin(theta1) * cos(theta0) / sin(theta0 + theta1);
	float tp01 = ts01 * cos(theta0 - theta1);

	// amplitude for inner reflection
	float rs12 = -sin(theta1 - theta2) / sin(theta1 + theta2);
	float rp12 = tan(theta1 - theta2) / tan(theta1 + theta2);

	// after passing through first surface twice:
	// 2 transmissions and 1 reflection
	float ris = ts01 * ts01 * rs12;
	float rip = tp01 * tp01 * rp12;

	// phase difference between outer and inner reflections
	float dy = d1 * n1;
	float dx = tan(theta1) * dy;
	float delay = sqrt(dx * dx + dy * dy);
	float relPhase = 4 * M_PI_F / lambda * (delay - dx * sin(theta0));

	// Add up sines of different phase and amplitude
	float out_s2 = rs01 * rs01 + ris * ris + 2 * rs01 * ris * cos(relPhase);
	float out_p2 = rp01 * rp01 + rip * rip + 2 * rp01 * rip * cos(relPhase);
	float reflectiviy = (out_s2 + out_p2) / 2;

	return reflectiviy;
}

// @brief	Returns a refraction vector given an incidence vector, a normal vector for a surface,
// 		and a ratio of indices of refraction at the surface's interface.
// 		The incidence vector i and normal vector n should be normalized.
// 		https://developer.download.nvidia.com/cg/refract.html
// 		https://graphics.stanford.edu/courses/cs148-10-summer/docs/2006--degreve--reflection_refraction.pdf
// @param i incidence vector
// @param n normal vector
// @param o refraction ratio (n1 / n2)
// @return Void.
float3 refract(
	float3 i,
	float3 n,
	float o
	)
{
	float sint2;  // sin(theta1)**2
	float cost;  // cos(theta1)
	float3 t;
	// cos(theta1) = dot(a, b) / (length(a) * length(b))
	// since a and b are normalized, cost = dot(a,b)
	cost = dot(-i, n);
	sint2 = (o * o) * (1 - cost * cost);
	t = (o * i) + (o * cost - sqrt(fabs(1 - sint2))) * n;
	// sometimes sint2 is above 1, abs() in the sqrt prevents crash. Then multiply by 0 since the ray is invalid.
	return t * (float)(sint2 < 1);
}


// @brief	Returns the reflectiton vector given an incidence vector i and a normal vector n.
// 		The normal vector n should be normalized.
// 		https://developer.download.nvidia.com/cg/reflect.html
// 		https://graphics.stanford.edu/courses/cs148-10-summer/docs/2006--degreve--reflection_refraction.pdf
// @param i incidence vector
// @param n normal vector
// @return Void.
float3 reflect(
	float3 i,
	float3 n
	)
{
	return i + 2.0f * dot(n, -i) * n;
}


// Returns the refractive index based on the material and wavelength
// https://en.wikipedia.org/wiki/Sellmeier_equation
float dispersion(
	float lambda,
	float8 coefficients
	)
{
	// lambda in nm
	// sellmeier equation requires lambda in micrometer
	lambda *= 1e-3;
	float l2 = lambda * lambda;
	float d0 = (coefficients.s0 * l2) / (l2 - coefficients.s1);
	float d1 = (coefficients.s2 * l2) / (l2 - coefficients.s3);
	float d2 = (coefficients.s4 * l2) / (l2 - coefficients.s5);
	return sqrt(1 + d0 + d1 + d2);
}


Intersection intersect(
	Ray ray,
	LensElement lens
	)
{
	Intersection i;

	if (ray.dir.z == 0) {
		i.hit = false;
	} else if (lens.radius == 0) {
		// flat intersection
		float dz = -lens.center - ray.pos.z;

		// |ray.dir| / distance to intersecion = dz / ray.dir.z
		i.pos = ray.pos + ray.dir * (dz / ray.dir.z);
		i.normal = (ray.dir.z < 0) ? (float3)(0, 0, 1) : (float3)(0, 0, -1);
		i.hit = true;
		i.incident = 0.0f;
	} else {
		// spherical intersection
		// https://www.bluebill.net/circle_ray_intersection.html
		// could be optimized by removing length() calls

		float r = fabs(lens.radius);
		float3 C = (float3)(0, 0, -lens.center);

		float3 U = C - ray.pos;
		float3 U1 = dot(U, ray.dir) * ray.dir;
		float d = length(U - U1);

		// discard ray if it doesn't hit the sphere
		if (d > r) {
			i.hit = false;
			return i;
		}

		float m = sqrt(r * r - d * d);
		float sgn = (lens.radius * ray.dir.z) > 0 ? -1 : 1;

		i.pos = ray.pos + U1 - (m * ray.dir) * sgn;
		i.normal = normalize(i.pos - C) * sgn;

		// dot(A, B) = |A||B|cos(theta)
		// theta = acos(dot(A, B) / |A||B|)
		// if A and B are unit vectors, |A||B| = 1
		// acos takes values from -1 to 1, otherwise nan
		i.incident = acos(clamp(dot(-ray.dir, i.normal), -1.0f, 1.0f));
		i.hit = true;
	}
	return i;
}


Ray init_ray(
	LensElement lens,
	int grid_count,
	float grid_length,
	float4 initial_direction
)
{
	int ray_id = get_global_id(2);

	// get grid point position
	int y = trunc((float) ray_id / grid_count);
	int x = ray_id - (y * grid_count);

	// x: left right, y: top down3
	float2 point_position;
	point_position.x = grid_length * ((float) x / (grid_count - 1) - 0.5);
	point_position.y = grid_length * (0.5 - (float) y / (grid_count - 1));

	// initialize ray
	// cast initial ray straight towards the first lens to get initial position
	// of the grid mapped onto the lens
	Ray ray;
	ray.pos = (float3) (point_position, 1);
	ray.dir = (float3) (0, 0, -1);

	Intersection i;
	i = intersect(ray, lens);

	// back up and set the actual direction.
	float3 direction = normalize(initial_direction.xyz * -1);
	ray.pos = i.pos - direction;
	ray.pos_apt = (float2) (0, 0);
	ray.dir = direction.xyz;
	ray.rrel = 0.0f;
	ray.reflectance = 1.0f;

	return ray;
}


__kernel void raytrace(
	__global Ray *rays,
	__constant LensElement *lenses,
	int lenses_count,
	__constant int2 *paths,
	int grid_count,
	float grid_length,
	float4 direction,
	__constant int *wavelengths
#if defined(STORE_INTERSECTIONS)
	, __global Intersection *intersections,
	int intersections_count
#endif
	)
{
	int path_id = get_global_id(0);
	int path_count = get_global_size(0);
	int wavelength_id = get_global_id(1);
	int wavelength_count = get_global_size(1);
	int ray_id = get_global_id(2);
	int ray_count = get_global_size(2);

	// rays = (path, wavelength, ray)
	int ray_index = ((path_id * wavelength_count + wavelength_id) * ray_count + ray_id);
	int2 path = paths[path_id];
	float wavelength = (float) wavelengths[wavelength_id];

	// initialize ray
	Ray ray = init_ray(lenses[0], grid_count, grid_length, direction);

	// step increases everytime a ray bounces, there are always 3 steps
	int step = 0;
	int inter_id = 0;
	int delta = 1;

	bool disperse = !isnan(lenses[0].coefficients.x);

	size_t lens_id;
	for (lens_id = 0; lens_id < lenses_count; inter_id++, lens_id += delta)
	{
		LensElement lens = lenses[lens_id];

		Intersection inter;
		inter = intersect(ray, lens);
		if(!inter.hit) {
			break;
		}

#if defined(STORE_INTERSECTIONS)
		int inter_index = ray_index * intersections_count + inter_id;
		intersections[inter_index] = inter;
#endif
		// update ray direction and position
		ray.pos = inter.pos;

		if (lens.is_apt) {
			ray.pos_apt = inter.pos.xy / lens.height;
			// skip refract/reflection for aperture
			continue;
		} else {
			ray.rrel = max(ray.rrel, length(inter.pos.xy) / lens.height);
		}

		// no reflection / refraction on sensor plane
		if (lens_id == lenses_count - 1) continue;

		// reverse direction of the ray
		bool do_reflect = false;
		if ((step == 0 && lens_id == path.x) || (step == 1 && lens_id == path.y)) {
			do_reflect = true;
			step++;
			delta = -delta;
		}

		// get previous index
		int n_index = (ray.dir.z < 0) ? lens_id - 1 : lens_id + 1;
		// if previous medium is outside lens system, set n1 = 1 (air)
		float n1 = (0 <= n_index && n_index < lenses_count) ? lenses[n_index].ior : 1;
		float n2 = lens.ior;

		// calculate dispersion on glass mediums (n>1)
		if (disperse && n1 > 1) {
			n1 = dispersion(wavelength, lenses[n_index].coefficients);
		}
		if (disperse && n2 > 1) {
			n2 = dispersion(wavelength, lens.coefficients);
		}

		if (do_reflect) {
			ray.dir = reflect(ray.dir, inter.normal);

			// optimal coating
			// 1.38 = lowest achievable refractive index (MgF2)
			// https://en.wikipedia.org/wiki/Anti-reflective_coating#Single-layer_interference
			// However there are better coatings available with refractive indexes as low as 1.12
			// refractive index of the coating
			// float nc = max(sqrt(n1 * n2), n_min);
			float nc = max(1.01f, lens.coating.y);

			// the wavelength that the coating is optimized for in vacuum
			float lambda = lens.coating.x;

			// the optimal effective thickness of the coating
			// https://en.wikipedia.org/wiki/Anti-reflective_coating#Interference_coatings
			float d1 = lambda / (4.0f * nc);

			// prevent divide by 0 errors
			float theta = inter.incident + 1e-9;

			// anti reflective coating
			// Supplemental Material — Physically-Based Real-Time Lens Flare Rendering
			float reflectance = fresnel_ar(
				theta,
				wavelength,
				d1,
				n1,
				nc,
				n2
			);
			if (reflectance > 0) {
				// ray.reflectance *= clamp(reflectance, 0.0f, 1.0f);
				ray.reflectance *= reflectance;
			}
		} else {
			float ratio = n1 / n2;
			ray.dir = refract(ray.dir, inter.normal, ratio);
			if(ray.dir.z == 0) {
				// total reflection
				break;
			}
		}
	}

	// early exit rays invalid
	if (lens_id < lenses_count) {
		ray.reflectance = NAN;
	}
	rays[ray_index] = ray;
}
