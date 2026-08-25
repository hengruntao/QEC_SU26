/* np_random.h
 *
 * Bit-exact reimplementation of NumPy's legacy RandomState generator, enough
 * to reproduce the two lines the Python decoders use:
 *
 *     np.random.seed(21)
 *     error = (np.random.rand(num_variable_node) < p).astype(int)
 *
 * That is MT19937 seeded with Knuth's initialiser (numpy's mt19937_seed, which
 * matches the reference init_genrand), and doubles drawn as
 *
 *     a = next_uint32() >> 5      (27 bits)
 *     b = next_uint32() >> 6      (26 bits)
 *     value = (a * 2^26 + b) / 2^53
 *
 * Keeping this exact is what lets the C decoder run on the same error pattern
 * as the Python reference, so the two outputs can be diffed line by line.
 */

#ifndef NP_RANDOM_H
#define NP_RANDOM_H

#define NP_MT19937_N 624

typedef struct {
    unsigned int key[NP_MT19937_N];
    int pos;
} np_random_state;

/* np.random.seed(seed) */
void np_random_seed(np_random_state *state, unsigned int seed);

unsigned int np_random_next_uint32(np_random_state *state);

/* one draw of np.random.rand() -- a double in [0, 1) */
double np_random_next_double(np_random_state *state);

/* np.random.rand(count) */
void np_random_rand(np_random_state *state, double *out, int count);

#endif /* NP_RANDOM_H */
