# Makefile for the C implementation of the Int4.2.8 CNU/VNU and the BP decoders.
#
#   make            build everything into build/bin
#   make run        build, then run every program
#   make check      build, then diff every program against the Python output
#   make clean      remove build/

CC       ?= cc
CFLAGS   ?= -std=c99 -O2 -Wall -Wextra -pedantic
CPPFLAGS += -Icnu -Ivnu -Iintegrated_cnu_vnu
LDLIBS   += -lm

BUILD := build
BIN   := $(BUILD)/bin

LIB_SRCS := cnu/cnu_int4.c \
            vnu/vnu_int4.c \
            integrated_cnu_vnu/gf2.c \
            integrated_cnu_vnu/matrix_generator.c \
            integrated_cnu_vnu/np_random.c \
            integrated_cnu_vnu/mem_strength.c \
            integrated_cnu_vnu/bp_common.c
LIB_OBJS := $(LIB_SRCS:%.c=$(BUILD)/%.o)

PROGS := cnu_int4_demo vnu_int4_demo unit_test_for_mult iterations_bp iterations_dmem_bp
BINS  := $(addprefix $(BIN)/,$(PROGS))

.PHONY: all run check clean
all: $(BINS)

$(BIN)/cnu_int4_demo:      $(BUILD)/cnu/cnu_int4_demo.o                    $(LIB_OBJS)
$(BIN)/vnu_int4_demo:      $(BUILD)/vnu/vnu_int4_demo.o                    $(LIB_OBJS)
$(BIN)/unit_test_for_mult: $(BUILD)/integrated_cnu_vnu/unit_test_for_mult.o $(LIB_OBJS)
$(BIN)/iterations_bp:      $(BUILD)/integrated_cnu_vnu/iterations_bp.o      $(LIB_OBJS)
$(BIN)/iterations_dmem_bp: $(BUILD)/integrated_cnu_vnu/iterations_dmem_bp.o $(LIB_OBJS)

$(BINS):
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -o $@ $^ $(LDLIBS)

$(BUILD)/%.o: %.c
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(CPPFLAGS) -MMD -MP -c -o $@ $<

run: $(BINS)
	@for p in $(PROGS); do \
		echo "===== $$p ====="; \
		$(BIN)/$$p; \
	done

# Golden files in tests/expected/ are the verbatim stdout of the Python
# reference scripts.  A clean diff means the port is byte-for-byte faithful.
check: $(BINS)
	@status=0; \
	for p in $(PROGS); do \
		if $(BIN)/$$p | diff -u tests/expected/$$p.txt - > /dev/null; then \
			echo "PASS  $$p"; \
		else \
			echo "FAIL  $$p"; \
			$(BIN)/$$p | diff -u tests/expected/$$p.txt - | head -40; \
			status=1; \
		fi; \
	done; \
	exit $$status

clean:
	rm -rf $(BUILD)

-include $(shell find $(BUILD) -name '*.d' 2>/dev/null)
