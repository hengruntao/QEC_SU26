SHELL := /bin/sh
BUILD ?= /tmp/qec-window-sim
IVERILOG ?= iverilog
VVP ?= vvp
VERILATOR ?= verilator
PYTHON ?= python3
CORE := ../IBM_OSS_decoder.srcs/sources_1/new
CORE_SOURCES := $(CORE)/cnu_pkg.sv $(CORE)/cnu.sv $(CORE)/vnu.sv $(CORE)/relay_bp_top.sv
WINDOW_SOURCES := relay_window_adapter.sv window_decoder_ctrl.sv window_effects.sv window_decoder_top.sv window_relay_top.sv
.PHONY: test test-effects test-relay test-matrices verify lint
test: test-effects test-relay

lint:
	$(VERILATOR) --lint-only --Wall --top-module window_decoder_ctrl window_decoder_ctrl.sv
	$(VERILATOR) --lint-only --Wall --replication-limit 16384 --top-module window_decoder_top window_decoder_ctrl.sv window_effects.sv window_decoder_top.sv
	$(VERILATOR) --lint-only --Wno-fatal --top-module relay_bp_top $(CORE_SOURCES)
	$(VERILATOR) --lint-only --Wno-fatal --top-module window_relay_top -GW=3 -GC=1 -GM=2 -GN_ERRORS=6 -GK=2 -GDC=3 -GDV=2 $(CORE_SOURCES) $(WINDOW_SOURCES)

.PHONY: test-relay
test-relay:
	$(PYTHON) test_established_relay.py --build "$(BUILD)/established"

.PHONY: test-relay-full
test-relay-full:
	$(PYTHON) test_established_relay.py --build "$(BUILD)/established" --only full

test-effects:
	$(PYTHON) run_rtl_tests.py --build "$(BUILD)/effects"

test-matrices:
	$(MAKE) -C matrices test PYTHON="$(PYTHON)"

verify: test-matrices test lint
