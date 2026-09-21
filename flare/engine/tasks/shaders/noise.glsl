// Sine-based hashes. Keep the input in roughly [0, 1];
float noise(float x) {
    return fract(sin(x * 12.9898) * 43758.5453);
}

float noise(vec2 pos) {
    return fract(sin(dot(pos, vec2(12.9898, 78.233))) * 43758.5453);
}

float noise(vec3 pos) {
    return fract(sin(dot(pos, vec3(127.1, 311.7, 74.7))) * 43758.5453);
}

float noise(vec4 pos) {
    return fract(sin(dot(pos, vec4(269.5, 183.3, 218.7, 142.3))) * 43758.5453);
}

// Integer hash (PCG).
uint pcg_hash(uint value) {
    uint state = value * 747796405u + 2891336453u;
    uint word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
    return (word >> 22u) ^ word;
}

// Return a uniform random number in [0, 1).
float random(uint seed) {
    return float(pcg_hash(seed)) / 4294967296.0;
}
