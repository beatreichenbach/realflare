// Convert a pixel position to uv space
vec2 convert_uv(vec2 pos, vec2 resolution) {
    return pos / (resolution - 1);
}

// Convert a pixel position to ndc space
vec2 convert_ndc(vec2 pos, vec2 resolution) {
    return (pos / resolution) * 2.0 - 1.0;
}

// Scale coordinates
vec2 scale(vec2 pos, vec2 scale) {
    return pos / max(scale, vec2(1e-8));
}

// Rotate coordinates
vec2 rot(vec2 pos, float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return vec2(c * pos.x - s * pos.y, s * pos.x + c * pos.y);
}

// Translate
vec2 trans(vec2 pos, vec2 offset) {
    return pos - offset;
}

// Draw a circle
float circle(vec2 pos, float radius) {
    return length(pos) - radius;
}

// Draw a rectangle
float rectangle(vec2 pos, vec2 half_size) {
    vec2 edge_distance = abs(pos) - half_size;
    float outside = length(max(edge_distance, 0.0));
    float inside = min(max(edge_distance.x, edge_distance.y), 0.0);
    return outside + inside;
}