# Makefile for the C implementation of the Int4.2.8 CNU/VNU and the BP decoders.
#
#   make            build everything into build/bin
#   make run        build, then run every program
#   make check      build, then verify against the Python reference
#   make generate   regenerate the code tables (needs an interpreter with qldpc)
#   make clean      remove build/

CC       ?= cc
CFLAGS   ?= -std=c99 -O2 -Wall -Wextra -pedantic
CPPFLAGS += -Icnu -Ivnu -Iintegrated_cnu_vnu
LDLIBS   +=

# Interpreter used by `make generate`.  qldpc is not in the default python3.
PYTHON ?= /opt/anaconda3/envs/relay_bp/bin/python

BUILD := build
BIN   := $(BUILD)/bin

LIB_SRCS := cnu/cnu_int4.c \
            vnu/vnu_int4.c \
            integrated_cnu_vnu/mem_strength.c \
            integrated_cnu_vnu/bp_decoder.c \
            integrated_cnu_vnu/bb_code_data.c \
            integrated_cnu_vnu/bp_test_data.c
LIB_OBJS := $(LIB_SRCS:%.c=$(BUILD)/%.o)

PROGS := cnu_int4_demo vnu_int4_demo unit_test_for_mult iterations_bp iterations_dmem_bp test_bp
BINS  := $(addprefix $(BIN)/,$(PROGS))

# Programs whose stdout is compared against a checked-in golden file.
DIFF_PROGS := cnu_int4_demo vnu_int4_demo unit_test_for_mult

.PHONY: all run check generate clean
all: $(BINS)

$(BIN)/cnu_int4_demo:      $(BUILD)/cnu/cnu_int4_demo.o                     $(LIB_OBJS)
$(BIN)/vnu_int4_demo:      $(BUILD)/vnu/vnu_int4_demo.o                     $(LIB_OBJS)
$(BIN)/unit_test_for_mult: $(BUILD)/integrated_cnu_vnu/unit_test_for_mult.o $(LIB_OBJS)
$(BIN)/iterations_bp:      $(BUILD)/integrated_cnu_vnu/iterations_bp.o      $(LIB_OBJS)
$(BIN)/iterations_dmem_bp: $(BUILD)/integrated_cnu_vnu/iterations_dmem_bp.o $(LIB_OBJS)
$(BIN)/test_bp:            $(BUILD)/integrated_cnu_vnu/test_bp.o            $(LIB_OBJS)

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

# Two kinds of verification:
#   - test_bp compares decoded values against the Python results baked into
#     bp_test_data.c, over every case and both decoders.
#   - the small programs are diffed against the verbatim Python stdout.
check: $(BINS)
	@status=0; \
	$(BIN)/test_bp || status=1; \
	for p in $(DIFF_PROGS); do \
		if $(BIN)/$$p | diff -u tests/expected/$$p.txt - > /dev/null; then \
			echo "PASS  $$p"; \
		else \
			echo "FAIL  $$p"; \
			$(BIN)/$$p | diff -u tests/expected/$$p.txt - | head -40; \
			status=1; \
		fi; \
	done; \
	exit $$status

# The generated tables are checked into git; this only needs rerunning if the
# code parameters change.
generate:
	cd integrated_cnu_vnu && $(PYTHON) export_bb_code.py

clean:
	rm -rf $(BUILD)

-include $(shell find $(BUILD) -name '*.d' 2>/dev/null)
