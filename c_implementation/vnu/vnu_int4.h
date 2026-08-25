#define VNU_MAX_DEG 6
#define MAX_VAL 15


typedef struct {
    int vnu_messages[VNU_MAX_DEG];
    int marginal;
    int hard_decision;
    int degree;
} vnu_result;

int vnu_hardware_int4(cnu)