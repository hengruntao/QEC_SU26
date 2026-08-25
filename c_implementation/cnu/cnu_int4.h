#define CNU_MAX_DEG 6
#define MAX_VAL 15

typedef struct {
    int min1_scaled;
    int min2_scaled;
    int signs_per_edge[CNU_MAX_DEG];
    int selectors_per_edge[CNU_MAX_DEG];
} cnu_result;

// degree is the length of vnu_messages
int cnu_hardware_int4(int* vnu_messages, int degree, int sigma_i, int t, cnu_result* cnu_result_ptr);
