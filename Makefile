PY ?= python3
ROOT ?= db
SCHEMAS ?= $(ROOT)/schemas
CONFIG ?= $(ROOT)/config.yaml
SPEC ?= src/fs_spec.yaml
# Working-mode output directory under the root
OUT ?= $(ROOT)/output
SITE ?= $(ROOT)/site
MAP ?= $(OUT)/collections.json
RELDB ?= $(OUT)/db.sqlite
DUMPSQL ?= $(OUT)/db_dump.sql

.PHONY: all fs collections relations map fkmap site maybe-clean clean rmsite cleanall clean-html re legacy test
.NOTPARALLEL: all

all: fs collections relations fkmap site clean

fs:
	$(PY) src/validate_fs.py --root $(ROOT) --spec $(SPEC)

collections map: fs
	@mkdir -p $(OUT)
	$(PY) src/validate_collections.py --root $(ROOT) --schemas $(SCHEMAS) --config $(CONFIG) --map-out $(MAP)

relations: collections
	@mkdir -p $(OUT)
	@echo "[relations] Building relations DB from $(MAP) -> $(RELDB)"
	@$(PY) src/validate_relations.py --map-in $(MAP) --db-out $(RELDB) --dump-sql $(DUMPSQL)

fkmap: relations
	@mkdir -p $(OUT)
	$(PY) src/map_foreign_keys.py --db $(RELDB) --out $(OUT)/fk_rows.json

site: relations
	@mkdir -p $(SITE)
	$(PY) src/render_site.py --root $(ROOT) --db $(RELDB) --out $(SITE)

clean:
	@if [ -z "$(KEEP_INTERMEDIATE)" ]; then \
	  echo "[cleanup] Removing intermediate output. Set KEEP_INTERMEDIATE=1 to keep."; \
	  rm -rf $(OUT); \
	else \
	  echo "[cleanup] Keeping intermediates as requested."; \
	fi

rmsite:
	@echo "[cleanup] Removing site files HTML etc."
	@rm -rf $(SITE)

cleanall: clean rmsite

# Run unit tests (hermetic, uses temporary dirs)
test:
	$(PY) -m unittest discover -s tests -p "test_*.py"

# End-to-end pipeline against sample data in docs/db_sample
keep:
	$(MAKE) all KEEP_INTERMEDIATE=1

# Legacy target using main.py
legacy re:
	rm -f *.sqlite && time $(PY) main.py $(ROOT)
