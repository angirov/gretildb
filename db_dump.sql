BEGIN TRANSACTION;
CREATE TABLE _authors (id TEXT PRIMARY KEY);
INSERT INTO "_authors" VALUES('jnanasrimitra');
CREATE TABLE _manuscripts (id TEXT PRIMARY KEY);
INSERT INTO "_manuscripts" VALUES('jnaa');
INSERT INTO "_manuscripts" VALUES('jna');
CREATE TABLE _manuscripts_works (
                _manuscripts_id TEXT,
                _works_id TEXT,
                PRIMARY KEY (_manuscripts_id, _works_id),
                FOREIGN KEY (_manuscripts_id) REFERENCES _manuscripts(id),
                FOREIGN KEY (_works_id) REFERENCES _works(id)
            );
INSERT INTO "_manuscripts_works" VALUES('jnaa','sarvasabdabhavacarca');
INSERT INTO "_manuscripts_works" VALUES('jnaa','advaitabinduprakarana');
INSERT INTO "_manuscripts_works" VALUES('jnaa','sakarasiddhisastra');
INSERT INTO "_manuscripts_works" VALUES('jnaa','sarvajnasiddhi');
INSERT INTO "_manuscripts_works" VALUES('jnaa','karyakaranabhavasiddhi');
INSERT INTO "_manuscripts_works" VALUES('jna','sarvasabdabhavacarca');
INSERT INTO "_manuscripts_works" VALUES('jna','advaitabinduprakarana');
INSERT INTO "_manuscripts_works" VALUES('jna','sakarasiddhisastra');
INSERT INTO "_manuscripts_works" VALUES('jna','sarvajnasiddhi');
INSERT INTO "_manuscripts_works" VALUES('jna','karyakaranabhavasiddhi');
INSERT INTO "_manuscripts_works" VALUES('jna','vyapticarca');
INSERT INTO "_manuscripts_works" VALUES('jna','anupalabdhirahasya');
INSERT INTO "_manuscripts_works" VALUES('jna','anekantacinta');
INSERT INTO "_manuscripts_works" VALUES('jna','ksanabhangadhyaya');
INSERT INTO "_manuscripts_works" VALUES('jna','yoginirnayaprakarana');
INSERT INTO "_manuscripts_works" VALUES('jna','apohaprakarana');
INSERT INTO "_manuscripts_works" VALUES('jna','bhedabhedapariksa');
INSERT INTO "_manuscripts_works" VALUES('jna','sakarasangrahasutra');
INSERT INTO "_manuscripts_works" VALUES('jna','isvaravada');
CREATE TABLE _works (id TEXT PRIMARY KEY);
INSERT INTO "_works" VALUES('sarvasabdabhavacarca');
INSERT INTO "_works" VALUES('advaitabinduprakarana');
INSERT INTO "_works" VALUES('sakarasiddhisastra');
INSERT INTO "_works" VALUES('sarvajnasiddhi');
INSERT INTO "_works" VALUES('karyakaranabhavasiddhi');
INSERT INTO "_works" VALUES('vyapticarca');
INSERT INTO "_works" VALUES('anupalabdhirahasya');
INSERT INTO "_works" VALUES('anekantacinta');
INSERT INTO "_works" VALUES('ksanabhangadhyaya');
INSERT INTO "_works" VALUES('yoginirnayaprakarana');
INSERT INTO "_works" VALUES('apohaprakarana');
INSERT INTO "_works" VALUES('bhedabhedapariksa');
INSERT INTO "_works" VALUES('sakarasangrahasutra');
INSERT INTO "_works" VALUES('isvaravada');
CREATE TABLE _works_authors (
                _works_id TEXT,
                _authors_id TEXT,
                PRIMARY KEY (_works_id, _authors_id),
                FOREIGN KEY (_works_id) REFERENCES _works(id),
                FOREIGN KEY (_authors_id) REFERENCES _authors(id)
            );
INSERT INTO "_works_authors" VALUES('sarvasabdabhavacarca','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('advaitabinduprakarana','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('sakarasiddhisastra','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('sarvajnasiddhi','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('karyakaranabhavasiddhi','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('vyapticarca','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('anupalabdhirahasya','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('anekantacinta','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('ksanabhangadhyaya','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('yoginirnayaprakarana','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('apohaprakarana','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('bhedabhedapariksa','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('sakarasangrahasutra','jnanasrimitra');
INSERT INTO "_works_authors" VALUES('isvaravada','jnanasrimitra');
COMMIT;
