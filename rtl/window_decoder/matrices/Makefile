PYTHON ?= python3
RELAY_ROOT ?= ../../../../relay
X_CIRCUIT = $(RELAY_ROOT)/tests/testdata/bicycle_bivariate/circuit=bicycle_bivariate_144_12_12_memory_X,distance=12,rounds=12,error_rate=0.001,noise_model=uniform_circuit,basis=CX,A=x^3+y+y^2,B=y^3+x+x^2.stim
Z_CIRCUIT = $(RELAY_ROOT)/tests/testdata/bicycle_bivariate/circuit=bicycle_bivariate_144_12_12_memory_Z,distance=12,rounds=12,error_rate=0.001,noise_model=uniform_circuit,basis=CX,A=x^3+y+y^2,B=y^3+x+x^2.stim
export PYTHONDONTWRITEBYTECODE = 1

.PHONY: generate test
generate:
	$(PYTHON) generate_window_matrices.py --circuit "$(X_CIRCUIT)" --basis X --output generated/x_checks
	$(PYTHON) generate_window_matrices.py --circuit "$(Z_CIRCUIT)" --basis Z --output generated/z_checks

test:
	$(PYTHON) test_window_matrices.py --circuit "$(X_CIRCUIT)" --basis X --generated generated/x_checks
	$(PYTHON) test_window_matrices.py --circuit "$(Z_CIRCUIT)" --basis Z --generated generated/z_checks
	$(PYTHON) test_window_matrices.py --cross-sectors generated
