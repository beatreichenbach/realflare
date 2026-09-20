#version 430 core
#extension GL_ARB_shader_draw_parameters : enable

struct Ray {
    vec3 pos;
    float rrel;
    vec3 dir;
    float reflectance;
    vec2 pos_apt;
    uint _pad[2];
};

struct Vertex {
    vec2 pos;
    vec2 uv;
    float rrel;
    float reflectance;
    float intensity;
};

struct Ghost {
    uint ray_offset;
    uint ray_count;
    uint tri_offset;
    uint tri_count;
};

uniform Params {
    uint wavelength_count;
    uint wavelength_sub_count;
    vec2 screen_scale;
    float ghost_scale;
    float intensity;
    float _pad[2];
};

layout(std430) buffer Ghosts {
    Ghost ghosts[];
};
layout(std430) buffer Rays {
    Ray rays[];
};
layout(std430) buffer Intensities {
    float intensities[];
};

layout(std430) buffer Mesh {
    uvec4 mesh[];
};
layout(std430) buffer Neighbors {
    uint neighbors[];
};

out VertexData {
    float rrel;
    float reflectance;
    float intensity;
    float wavelength_pos;
    vec2 uv;
} v_out;


// Return the vertex attributes of a Ray.
Vertex get_vertex(Ray ray) {
    uint ghost_id = gl_DrawIDARB;
    uint wavelength_sub_id = gl_InstanceID;
    uint wavelength_id = wavelength_sub_id / wavelength_sub_count;
    uint ray_id = gl_VertexID;

    uint tri_offset = ghosts[ghost_id].tri_offset;
    uint tri_count = ghosts[ghost_id].tri_count;

    float area_intensity = 0.0;
    uint valid_neighbors = 0u;
    uint neighbor_offset = ray_id * 6u;
    uint wavelength_tri_offset = (tri_offset * wavelength_count) + (wavelength_id * tri_count);
    for (uint i = 0u; i < 6u; ++i) {
        uint neighbor = neighbors[neighbor_offset + i];
        if (neighbor < 0) break;

        uint prim_index = wavelength_tri_offset + neighbor;
        if (intensities[prim_index] > 0.0) {
            area_intensity += intensities[prim_index];
            ++valid_neighbors;
        }
    }
    area_intensity /= max(valid_neighbors, 1u);

    Vertex vertex;
    vertex.pos =  ray.pos.xy * screen_scale;
    vertex.uv = (ray.pos_apt / ghost_scale + 1.0) / 2.0 ;
    vertex.rrel = ray.rrel;
    vertex.reflectance = ray.reflectance;
    vertex.intensity = area_intensity;

    return vertex;
}


void main() {
    uint ghost_id = gl_DrawIDARB;
    uint wavelength_sub_id = gl_InstanceID;
    uint ray_id = gl_VertexID;
    uint ray_offset = ghosts[ghost_id].ray_offset;
    uint ray_count = ghosts[ghost_id].ray_count;

    // Get previous and next Ray
    uint wavelength_id = wavelength_sub_id / wavelength_sub_count;
    uint ray_index1 = (ray_offset * wavelength_count) + (wavelength_id * ray_count) + ray_id;

    wavelength_id = min(wavelength_id + 1u, wavelength_count - 1u);
    uint ray_index2 = (ray_offset * wavelength_count) + (wavelength_id * ray_count) + ray_id;

    // Get vertices
    Vertex vertex1 = get_vertex(rays[ray_index1]);
    Vertex vertex2 = get_vertex(rays[ray_index2]);

    // Blend vertices
    float blend = float(wavelength_sub_id % wavelength_sub_count) / float(wavelength_sub_count);
    gl_Position = vec4(mix(vertex1.pos, vertex2.pos, blend), 0.0, 1.0);
    // For sub wavelengths, it is possible that one vertex is invalid.
    float reflectance1 = isinf(vertex1.reflectance) ? 0 : vertex1.reflectance;
    float reflectance2 = isinf(vertex2.reflectance) ? 0 : vertex2.reflectance;
    v_out.uv = mix(vertex1.uv, vertex2.uv, blend);
    v_out.rrel = mix(vertex1.rrel, vertex2.rrel, blend);
    v_out.intensity = mix(vertex1.intensity, vertex2.intensity, blend);
    v_out.reflectance = mix(reflectance1, reflectance2, blend);

    uint total_sub_count = wavelength_count * wavelength_sub_count;
    v_out.wavelength_pos = wavelength_count > 1 ? (float(wavelength_sub_id) + 0.5) / float(total_sub_count) : -1.0;
}
