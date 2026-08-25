/* vnu_int4.h
 *
 * C port of vnu_python/vnu_int4.py -- the VNU (variable node unit) in Int4.2.8
 * fixed-point precision.  Behaviour is bit-for-bit identical to the Python
 * reference; see that file for the full derivation and commentary.
 */

#ifndef VNU_INT4_H
#define VNU_INT4_H

/* Largest variable-node degree (column weight of H) a single VNU can process.
 * The gross code [[144,12,12]] has column weight 6; 16 leaves plenty of room. */
#ifndef VNU_MAX_DEGREE
#define VNU_MAX_DEGREE 16
#endif

/* Max value an unsigned int4 can represent.
 * reference: FPGA paper, Fig 5 table (4-bit int + sign) */
#define VNU_MAX_VALUE 15

/* One message arriving from a neighboring CNU. */
typedef struct {
    int sign;           /* 0 or 1 */
    int selector;       /* 0 or 1 */
    int min1_scaled;
    int min2_scaled;
} cnu_message_t;

typedef struct {
    int degree;                          /* number of incident edges (d_v)   */
    int vnu_messages[VNU_MAX_DEGREE];    /* int4, nu_{j->i} for each edge    */
    int marginal;                        /* M_j (clamped to +/- 15)          */
    int hard_decision;                   /* 0 or 1, e_hat_j                  */
} vnu_result_t;

/*
 * VNU: processes one variable node (one column of H).
 *
 * Inputs:
 *     cnu_messages : array of cnu_message_t, one entry per neighboring CNU.
 *     degree       : int, length of cnu_messages, in [1, VNU_MAX_DEGREE].
 *     lambda_j     : int
 *                    Error prior Lambda_j(0) = log((1-p_j)/p_j)
 *                    Lambda_j(t) = (1-gamma_j)*Lambda_j(0) + gamma_j*M_j(t-1)
 *     result       : out parameter, filled in on success.
 *
 * IMPORTANT:
 *     IT IS the CALLER's responsibility to pass in-scale lambda_j
 *
 * Returns 0 on success, -1 if degree is out of range.
 */
int vnu_hardware_int4(const cnu_message_t *cnu_messages, int degree,
                      int lambda_j, vnu_result_t *result);

#endif /* VNU_INT4_H */
