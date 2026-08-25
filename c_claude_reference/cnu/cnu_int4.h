/* cnu_int4.h
 *
 * C port of cnu_python/cnu_int4.py -- the CNU (check node unit) in Int4.2.8
 * fixed-point precision.  Behaviour is bit-for-bit identical to the Python
 * reference; see that file for the full derivation and commentary.
 */

#ifndef CNU_INT4_H
#define CNU_INT4_H

/* Largest check-node degree (row weight of H) a single CNU can process.
 * The gross code [[144,12,12]] has row weight 6; 16 leaves plenty of room. */
#ifndef CNU_MAX_DEGREE
#define CNU_MAX_DEGREE 16
#endif

/* Saturation limit of the Int4.2.8 datapath: max value of an unsigned int4.
 * reference: FPGA paper, Fig 5 table (4-bit int + sign) */
#define INT4_MAX_VALUE 15

typedef struct {
    int degree;                     /* number of incident edges (d_c)        */
    int min1_scaled;                /* alpha * min1, shared across all edges */
    int min2_scaled;                /* alpha * min2, shared across all edges */
    int signs[CNU_MAX_DEGREE];      /* per-edge output sign bit     (0 or 1) */
    int selectors[CNU_MAX_DEGREE];  /* per-edge selector bit        (0 or 1) */
} cnu_result_t;

/*
 * CNU: processes one check node (one row of H)
 * input as "v", output as "miu"
 *
 * Inputs:
 *     vnu_messages : array of int, range [-15, +15] for int4.2.8
 *                    Incoming messages v_{j->i} from neighboring variable nodes.
 *     degree       : int, length of vnu_messages, in [1, CNU_MAX_DEGREE].
 *     sigma_i      : int (0 or 1) 1 means parity check detects an odd number of errors
 *                    Syndrome/detector bit for this check node. (message from QPU)
 *     t            : int (>= 1), BP iteration index.
 *                    Determines alpha = 1 - 2^(-t).
 *     result       : out parameter, filled in on success.
 *
 * IMPORTANT concept:
 *     sigma_i is the ONLY ground truth (message from the stabilizer in QPU)
 *     vnu_messages are ONLY guesses!!
 *
 * Returns 0 on success, -1 if degree or t is out of range.
 */
int cnu_hardware_int4(const int *vnu_messages, int degree, int sigma_i, int t,
                      cnu_result_t *result);

#endif /* CNU_INT4_H */
