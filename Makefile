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

.PHONY: all fs collections relations map fkmap site maybe-clean clean rmsite cleanall clean-html re legacy test fake-attachments clean-fake-attachments
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

site: relations fkmap
	@mkdir -p $(SITE)
	$(PY) src/render_site.py --root $(ROOT) --fkmap $(OUT)/fk_rows.json --collections $(MAP) --out $(SITE)

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

###########################################
# Generate random TXT attachments for all items in _works
# Tunables: FAKE_TAG, FAKE_COUNT, FAKE_HASH
FAKE_TAG ?= fake
FAKE_COUNT ?= 1
FAKE_HASH ?= 5
fake-attachments:
	$(PY) docs/scripts/gen_fake_attachments.py --root $(ROOT) --collection _works \
	  --tag $(FAKE_TAG) --per-item $(FAKE_COUNT) --hash-len $(FAKE_HASH)

# Remove all fake TXT attachments for a collection (default: _works)
FAKE_COLLECTION ?= _works
clean-fake-attachments:
	@echo "[fake] Cleaning fake attachments matching '*_$(FAKE_TAG)-*.txt' in $(ROOT)/$(FAKE_COLLECTION)"
	@count=$$(find $(ROOT)/$(FAKE_COLLECTION) -type f -name "*_$(FAKE_TAG)-*.txt" 2>/dev/null | wc -l); \
	 find $(ROOT)/$(FAKE_COLLECTION) -type f -name "*_$(FAKE_TAG)-*.txt" -delete 2>/dev/null || true; \
	 echo "[fake] Removed $$count file(s)."
