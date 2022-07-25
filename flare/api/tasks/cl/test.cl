__kernel void get_buffer_size(
	__global float *debug
)
{
	int index = get_global_id(0);
	debug[index] = (float) index;
}
