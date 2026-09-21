#version 430 core

const vec2 verts[3] = vec2[](
    vec2(-1.0, -1.0),
    vec2( 3.0, -1.0),
    vec2(-1.0,  3.0)
);
out vec2 uv;

void main() {
    vec2 pos = verts[gl_VertexID];
    gl_Position = vec4(pos, 0.0, 1.0);
    uv = (pos + 1.0) * 0.5;
}
