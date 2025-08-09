# scripts

## Ontology
- work
- author

works and authors have to have unique ID's 
works' and authors' titles/names in ASCII

They are related to each other by metadata files

For each work there is a one metadata `yaml` 
Each metadata `yaml` file refers to a list of authors 
Each referred author must have an author file

There are `json`/`yaml` schemas for work-metadata and author files.

The IDs must be related to one of the names/titles of the author/work, 
e.g. ID must be the first name/title's mapping of IAST to lower case stripped off diacritics.

max length of a file name: 255?

## Example

Minimal example

```
.
├── authors
│   └── jnanasrimitra.yaml
└── works
    ├── isvaravada.txt
    └── isvaravada.yaml

```
