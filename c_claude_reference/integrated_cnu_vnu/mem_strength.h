/* mem_strength.h
 *
 * ---- DMem-BP memory strength setup ----
 * Lambda_j(t) = (1-gamma_j)*Lambda_j(0) + gamma_j*M_j(t-1)
 * beta = (1-gamma) in [0, 2]
 * mu_int*gamma -> floor(mu_int*gamma_int/M)
 * gamma_int := floor(gamma*M)
 * mu_int*gamma -> floor(mu_int*(M-beta_int)/M)
 * beta_int := floor(beta*M)
 *
 * The Python side defines memory_strength_mult() twice, identically, in
 * iterations_dmem_bp.py and unit_test_for_mult.py.  Here it lives once and
 * both C programs link against it.
 */

#ifndef MEM_STRENGTH_H
#define MEM_STRENGTH_H

#define MEM_STRENGTH_SCALE_FACTOR 8    /* M -- the 8 in Int4.2.8            */
#define MEM_STRENGTH_NUM_SHIFT    3    /* /8 = right shift by 3             */
#define MEM_STRENGTH_BETA_INT     7    /* beta_int  = round(0.875 * 8) = 7  */
#define MEM_STRENGTH_GAMMA_INT    1    /* gamma_int = round(0.125 * 8) = 1  */

/* gamma_0 = 0.125, memory strength; value from FPGA paper, fig7 */
#define MEM_STRENGTH_GAMMA_0 0.125

/* From FPGA paper (optimization of multiplication)
 * We further reduce the logic requirements by simplifying the multiplication:
 * Instead of implementing a full multiplier for mu_int * beta_int,
 * we expand each bit of the bitwise representation of mu_int to beta_int,
 * shift right by m places, then null all effective fractional bits before
 * summing resulting values for the total result. */
int memory_strength_mult(int v, int coeff);

#endif /* MEM_STRENGTH_H */
