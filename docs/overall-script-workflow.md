# FS validation
1. the auxiliary files and folders scrtucture is validated (excluding the content of config file and the collection dirs with their files)
2. read and validate config file itself
3. for every collection dir:
    - check for disallowed files
    - validate the schema and naming pattern of (YAML)
    - validate naming pattern of the attachments
    - run the attachment scripts