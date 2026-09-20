#version 430 core

struct Intersection {
    vec3 pos;
    float incident;
    vec3 normal;
    bool hit;
};

uniform Params {
    float height;
    float scale;
    uint ray_id_count;
    uint intersection_count;
};

layout(std430) buffer Intersections {
    Intersection intersections[];
};

layout(std430) buffer RayIDs {
    uint ray_ids[];
};

uniform sampler2D background;

in vec2 uv;
out vec4 rgba;

// Return an sdf of a line.
float line(vec2 uv, vec2 a, vec2 b)
{
    vec2 uva = uv - a;
    vec2 ba = b - a;
    float h = clamp(dot(uva, ba) / dot(ba, ba), 0.0, 1.0);
    return length(uva - ba * h);
}

void main() {
    float padding = 1.0;
    vec2 pos = vec2(gl_FragCoord.x, height / 2.0 - gl_FragCoord.y) / scale;
    pos.x -= padding;

    float blur = 0.5 / scale;
    float thickness = 0.8 / scale;
    float normal_length = 10.0 / scale;

    vec3 rgb = vec3(0.0, 0.0, 0.0);
    vec3 normal_color = vec3(0.25, 0, 0);
    vec3 ray_color = vec3(0.6, 0.6, 0.6);

    for (uint i = 0u; i < ray_id_count; i++) {
        uint ray_id = ray_ids[i];
        uint offset = intersection_count * ray_id;

        for (uint inter_id = 0u; inter_id < intersection_count - 1u; inter_id++) {
            Intersection inter1 = intersections[offset + inter_id];
            Intersection inter2 = intersections[offset + inter_id + 1u];

            if (!inter2.hit) {
                break;
            }

            vec2 start = inter1.pos.zx * -1.0;
            vec2 end = inter2.pos.zx * -1.0;

            // Draw ray
            float sdf = line(pos, start, end);
            vec3 color = ray_color * smoothstep(thickness + blur, thickness - blur, sdf);
            rgb = max(rgb, color);

            // Draw normal
            vec2 normal = inter1.normal.zx;
            vec2 point_normal = start - normal * normal_length;
            sdf = line(pos, start, point_normal);
            color = normal_color * smoothstep(thickness + blur, thickness - blur, sdf);
            rgb = max(rgb, color);
        }
    }

    rgb = max(texture(background, uv).xyz, rgb);
    rgba = vec4(rgb, 1.0);
}
