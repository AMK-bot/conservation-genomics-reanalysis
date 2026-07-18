# Sendable website bundle validation

The project portfolio is packaged as one deterministic ZIP with its complete local link closure.

**Summary: 10 PASS, 0 FAIL**

| check | status | evidence |
|---|---|---|
| complete website dependency closure | **PASS** | 83 local website targets; 136 project files |
| no external runtime dependency | **PASS** | all CSS, JavaScript, fonts, images, and embedded report assets are local |
| deterministic construction | **PASS** | two independent in-memory builds are byte-identical |
| ZIP integrity | **PASS** | all compressed members pass CRC |
| safe portable archive paths | **PASS** | portable member paths and modes |
| portable executable modes | **PASS** | all 6 runnable source scripts retain mode 0755 |
| exact SHA-256 manifest | **PASS** | all 137 non-manifest members match SHA-256 |
| fresh extraction | **PASS** | conservation-genomics-portfolio/index.html is ready to open |
| cross-file HTML anchors | **PASS** | 47 HTML fragment links checked |
| extracted website validation | **PASS** | 10 PASS, 0 FAIL after fresh extraction |

## Bundle

- Archive: `dist/conservation-genomics-portfolio.zip`
- Compressed size: 3,283,617 bytes
- ZIP entries: 138
- Bundled project files: 136
- Website-local targets: 83
- SHA-256: `4154c7bec66ff77405da3278c842a9e640da138c7bac3d233f7daaa1fa5d0890`

The bundle excludes raw public genomic datasets and regenerable intermediates; these are not
website dependencies. External DOI citations require internet only when opened.
