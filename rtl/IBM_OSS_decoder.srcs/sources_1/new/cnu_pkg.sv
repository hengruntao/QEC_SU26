package cnu_pkg;

typedef struct packed {
    logic sign; //this refers to the (K_i,j . (-1)^σ_i) or the sign
    logic c;    //selector bit to resolve absolute min, 0=min1 and 1=min2
    logic [3:0] min1; //int4 magnitude
    logic [3:0] min2; //int4 magnitude
} cnu_msg_t;

endpackage
