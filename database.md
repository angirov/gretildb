# Database (going abstract)

## Key ideas
The DB is strictly text based and human reader and editor friendly.
The format is originally designed to store information about immutable properties of immutable entities and relations between immutable entities (like historical documents). The changes are conditioned by limitations of our knowledge and editorial mistakes. So no IRT capabilities are not relevant. Performance issues have tolerance of seconds to few minutes. 
The integrity and consistency of data is provided by simple scripts and version control and collaboration systems like `git` and CI (continuous integration) instruments like `GitHub Actions`. VCS like `git` also allow to track the authorship of changes which could be important in scholastic and academic context.

## Directories
There is a root dir contains: 

1. the DB config file
2. subdirs representing collections of documents begin with `_`
3. `schemas` folder containing one schema for each collection 

Subfolders within the collection subdirs are optional and serve only human convenience (The file system mechanisms providing the uniqueness of doc names (==keys) are not enough because of for our DB lower/upper case should not be relevant and integrity across multiple projects should be also possible, so further checks are necessary anyway).

TODO: .dirinfo.yaml optional?

## Data model
The `data model` (entities and their relations) should be decuctible from the `schemas` dir. Entities are decucted from collection dirs and corresponding schema files. Relations are decucted from the foreign key properties required in the schema files.

## Collections
Collection name is meaningful noun in plural

## Documents and keys
Documents are incarnated as `yaml` files. The doc key is the stem of the file name. They only consists of lowercase ASCII symbols and dash separators (`^[a-z][-a-z]*[a-z]$`) - they have to be URL compatible. Keys must be unique within the collection. Foreign key only refer to existing documents in a collection.Foreign keys are referred to by properties that begin with `_` and contain (!) a noun corresponding to an existing collection, in singular if the property is a single string and in plural if it is a string array. These propertie names should also suggest the nature of the relation, e.g. `_composedby-authors`, `_containing-works`. Schemas have a description for foreign key properties, explaining the semantic relation between entities.

## Attachments
The documents may have text files as attachments. The relation of attachments to documents is established by file naming conventions only, e.g. `<document key>_<attachment id>_<part id>.txt`. Doc and attachment must belong to the same immediate folder.
TODO: how to keep track of the attachment format?

Schemas forbit additional properties. Numbers are only recorded in numeric types.

## Scaling
There should be some mechanisms for keeping integrity between multiple related projects (same data model). based on the specialization of their maintainers and contributors (e.g. language and particular subject, e.g. Sanskrit Buddhist Shastra). 

TODO: I guess some subordination between related projects is necessary... or not?

## Representation
The DB should be able to **authomatically** translated into static `html` documents for serving to non-technical users. They can be easily hosted e.g. via `GitHub Pages`.

## Compatibility
Our DB should be easily be loaded into real 'adult' RDBMSs like SQLite or PostgresQL. Perhaps this should be a step in integration tests.

## Conventions

1. 
2. `yaml` files are for human editing and reading. `json` files are machine generated and consumed.
3. Separator `-` is used for readability. `_` is used as technical marker or separator.
