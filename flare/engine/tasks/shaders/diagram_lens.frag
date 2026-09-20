#version 430 core

#define STOP 0
#define STANDARD 1
#define EVEN_ASPHERIC 2
#define EXTENDED_ASPHERIC 3
#define EXTENDED_ODD_ASPHERIC 4
#define CYLINDER_X 5
#define CYLINDER_Y 6

struct Surface {
    uint type;
    float center;
    float radius;
    float height;
    vec4 coefficients;
    float conic;
    float coating_wavelength;
    float coating_ior;
    float _pad;
};

uniform Params {
    vec2 resolution;
    float scale;
    uint surface_count;
};

layout(std430) buffer Surfaces {
    Surface surfaces[];
};
layout(std430) buffer Iors {
    float iors[];
};

out vec4 rgba;

// Return an sdf for a circle.
float circle(
    vec2 uv,
    vec2 center,
    float radius
) {
    return length(uv - center) - radius;
}

// Return an sdf for a rectangle.
float rectangle(
    vec2 uv,
    vec2 center,
    vec2 size
) {
    vec2 d = abs(uv - center) - size * 0.5;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

// Return an sdf of a lens.
float lens(
    vec2 pos,
    Surface front,
    Surface back
) {
    float y = 0.0;
    float mask = 0.0;

    // ((
    if (front.type == CYLINDER_X || back.type == CYLINDER_X) {
        mask = 10.0;
    }

    // ((
    else if (front.radius > 0 && back.radius > 0) {
        float a = circle(pos, vec2(front.center, y), front.radius);
        float b = circle(pos, vec2(back.center, y), back.radius);
        mask = max(a, -b);
    }
    // ()
    else if (front.radius > 0 && back.radius < 0) {
        float a = circle(pos, vec2(front.center, y), front.radius);
        float b = circle(pos, vec2(back.center, y), abs(back.radius));
        mask = max(a, b);

    }
    // )(
    else if (front.radius < 0 && back.radius > 0) {
        float x = (back.center + front.center) / 2.0;
        float width = back.center - front.center;
        float height = max(front.height, back.height) * 2.0;
        float a = rectangle(pos, vec2(x, y), vec2(width, height));
        float b = circle(pos, vec2(front.center, y), abs(front.radius));
        float c = circle(pos, vec2(back.center, y), back.radius);
        mask = max(max(a, -b), -c);
    }
    // ))
    else if (front.radius < 0 && back.radius < 0) {
        float a = circle(pos, vec2(back.center, y), abs(back.radius));
        float b = circle(pos, vec2(front.center, y), abs(front.radius));
        mask = max(a, -b);
    }
    // TODO: handle straight glasses
//    if (front.radius == 0 || back.radius == 0) {
//        float x = (back.center + front.center) / 2.0;
//        float width = back.center - front.center;
//        float height = max(front.height, back.height);
//        mask = rectangle(pos, vec2(x, y), vec2(width, height * 2));
//    }

    float left = front.center - front.radius;
    if (front.radius < 0) {
        float d = sqrt(max(front.radius * front.radius - front.height * front.height, 0.0));
        left = front.center + d;
    }

    float width = back.center - back.radius - left;
    if (back.radius > 0) {
        float d = sqrt(max(back.radius * back.radius - back.height * back.height, 0.0));
        width = back.center - d - left;
    }

    float x = left + width / 2.0;
    float height = max(front.height, back.height) * 2.0;

    float box = rectangle(pos, vec2(x, y), vec2(width, height));
    float sdf = max(mask, box);
    return sdf;
}

// Return the sdf of a line (aperture, sensor).
float line(vec2 pos, Surface surface) {
    float width = 4.0 / scale;
    float height = surface.height * 2.0;
    float x = surface.center + width / 2.0;
    float y = 0.0;
    float sdf = rectangle(pos, vec2(x, y), vec2(width, height));
    return sdf;
}

void main() {
    float padding = 1.0;
    vec2 pos = vec2(gl_FragCoord.x, resolution.y / 2 - gl_FragCoord.y) / scale;
    pos.x -= padding;

    float blur = 0.1 / scale;
    float border = 2.0 / scale;

    vec3 glass_color = vec3(0.1, 0.15, 0.25);
    vec3 aperture_color = vec3(0.1, 0.25, 0.1);
    vec3 sensor_color = vec3(0.1, 0.25, 0.1);
    vec3 border_color = vec3(0.2, 0.25, 0.35);

    vec3 rgb = vec3(0, 0, 0);
    vec3 color;
    float sdf;

    // Lens Elements
    for(uint i = 0; i < surface_count - 1; i++) {
        if (surfaces[i].type == STOP) {
            sdf = line(pos, surfaces[i]);
            color = aperture_color * smoothstep(0.0, blur, -sdf);
            rgb = max(rgb, color);
        }
        if (iors[i] > 1.0){
            sdf = lens(pos, surfaces[i], surfaces[i + 1]);
            color = glass_color * smoothstep(0.0, blur, -sdf);
            rgb = max(rgb, color);

            color = border_color * smoothstep(border + blur, -blur, abs(sdf));
            rgb = max(rgb, color);
        }
    }

    // Sensor
    sdf = line(pos, surfaces[surface_count - 1]);
    color = sensor_color * smoothstep(0.0, blur, -sdf);
    rgb = max(rgb, color);

    rgba = vec4(rgb, 1.0);
}
