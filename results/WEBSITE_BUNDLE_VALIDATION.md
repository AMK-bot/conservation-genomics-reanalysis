# Sendable website bundle validation

The project portfolio is packaged as one deterministic ZIP with its complete local link closure.

**Summary: 10 PASS, 0 FAIL**

| check | status | evidence |
|---|---|---|
| complete website dependency closure | **PASS** | 144 local website targets; 224 project files |
| no external runtime dependency | **PASS** | all CSS, JavaScript, fonts, images, and embedded report assets are local |
| deterministic construction | **PASS** | two independent in-memory builds are byte-identical |
| ZIP integrity | **PASS** | all compressed members pass CRC |
| safe portable archive paths | **PASS** | portable member paths and modes |
| portable executable modes | **PASS** | all 7 runnable scripts and launchers retain mode 0755 |
| exact SHA-256 manifest | **PASS** | all 225 non-manifest members match SHA-256 |
| fresh extraction | **PASS** | conservation-genomics-reanalysis/index.html is ready to open |
| cross-file HTML anchors | **PASS** | 66 HTML fragment links checked |
| extracted website validation | **PASS** | 30 PASS, 0 WARN, 0 FAIL after fresh extraction |

## Bundle

- Archive: `dist/conservation-genomics-reanalysis.zip`
- Compressed size: 8,269,343 bytes
- ZIP entries: 226
- Bundled project files: 224
- Website-local targets: 144
- SHA-256: `182eb844db02022cabb36d4b39cf8d42ad7dd20200b213a035cacf932dec3627`

The bundle excludes raw public genomic datasets and regenerable intermediates; these are not
website dependencies. External DOI citations require internet only when opened.
