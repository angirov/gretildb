PY ?= python3
ROOT ?= db
SCHEMAS ?= $(ROOT)/schemas
CONFIG ?= $(ROOT)/config.yaml
SPEC ?= src/fs_spec.yaml
# Working-mode output directory under the root
OUT ?= $(ROOT)/output
MAP ?= $(OUT)/collections.json
RELDB ?= $(OUT)/db.sqlite
DUMPSQL ?= $(OUT)/db_dump.sql

.PHONY: all fs collections relations map fkmap clean re legacy test test-pipeline clean-test

all: fs collections relations

fs:
	$(PY) src/validate_fs.py --root $(ROOT) --spec $(SPEC)

collections map:
	@mkdir -p $(OUT)
	$(PY) src/validate_collections.py --root $(ROOT) --schemas $(SCHEMAS) --config $(CONFIG) --map-out $(MAP)

relations:
	@mkdir -p $(OUT)
	@echo "[relations] Building relations DB from $(MAP) -> $(RELDB)"
	@$(PY) src/validate_relations.py --map-in $(MAP) --db-out $(RELDB) --dump-sql $(DUMPSQL); \
	status=$$?; \
	if [ $$status -eq 0 ] && [ -z "$(KEEP_INTERMEDIATE)" ]; then \
	  $(MAKE) clean; \
	else \
	  echo "[relations] Keeping intermediate artifacts (status $$status)."; \
	fi; \
	exit $$status

fkmap:
	@mkdir -p $(OUT)
	$(PY) src/map_foreign_keys.py --db $(RELDB) --out $(OUT)/fk_rows.json

clean:
	rm -f $(RELDB) $(DUMPSQL) $(MAP)
	-@rmdir $(OUT) 2>/dev/null || true

# Run unit tests (hermetic, uses temporary dirs)
test:
	$(PY) -m unittest discover -s tests -p "test_*.py"

# End-to-end pipeline against sample data in docs/db_sample
keep:
	$(MAKE) all KEEP_INTERMEDIATE=1

# Legacy target using main.py
legacy re:
	rm -f *.sqlite && time $(PY) main.py $(ROOT)
