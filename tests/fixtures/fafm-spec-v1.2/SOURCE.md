# Vendored: `.fafm` v1.2 conformance corpus

Copied byte-for-byte from [`Wolfe-Jam/faf`](https://github.com/Wolfe-Jam/faf) at commit
`0277dc2` ("spec(fafm): v1.2", merged 2026-11-04). Do not edit these files here; re-vendor
from a newer spec commit instead and update this note.

| Here | Upstream path |
|------|---------------|
| `fafm.schema.json` | `schemas/fafm.schema.json` |
| `expected.json` | `conformance/expected.json` (the runner reads its `fafm` section) |
| `valid/*.fafm`, `invalid/*.fafm` | `conformance/fafm/valid/`, `conformance/fafm/invalid/` |
| `txt_hash-vectors.json` | `conformance/fafm/txt_hash-vectors.json` |

Runner: `tests/test_fafm_spec_conformance.py`. SHA-256 of each vendored file:

```
5abf29370249cea1683492acbcfe23514c9e82c0654d2dd52af390fa8f8b50fa  ./expected.json
a4a050f41b89a014e28d1e9bade8993e30f47431b9b8b8b86d7d4171c41b7fbd  ./fafm.schema.json
459bf2c0193fc8a002ea1e75b508169c76c9093a6d747d7c98edbec369408d40  ./invalid/bad-version.fafm
9d48c567df71222d217a820940488f9ec67c8804169d069db2912519dced56d3  ./invalid/fact-missing-text.fafm
4e535eae801b08947fad6df3554941b24df524fde9c097aa4488cceba9e108e9  ./invalid/missing-required.fafm
653c0f73e0d1bc88a150f2e879584c81e9ca781ecbba1deeeab9eecbfd592e85  ./invalid/tombstone-non-utc.fafm
b34517760756413ae3dbd9bf2ccc555ec912b4ee7077b439ccd1e77fbcaa748f  ./invalid/tombstone-with-text.fafm
9bd2fcc3482be49b250cf331450092a7c8a0f587a4a393c6f59135647f4b25b2  ./invalid/unknown-profile.fafm
43fcb1cf3dfbbb47946c994d9a4fb08ec8ded69e06d647b3c029006f2213cdc7  ./txt_hash-vectors.json
030ea850cda228d764200cd9c0c01f4c0b856846ed64798d090b34a6bd2a061d  ./valid/knowledge.fafm
3a5514a1f84da6d33fc30ea0da322769afa5fd7991e4c221effa1b7500dc814b  ./valid/say-and-tombstones.fafm
4a10ff59cf59fc7766da01dc875be7eb156acc5323afa43d9fe30ef58ac7b7c2  ./valid/unknown-fields.fafm
adc848170a6e999805c2f64c20856a8882508d38491965ebb1ba18c0d0f472a3  ./valid/unknown-priority.fafm
362944322f245c3e903129f23d34991b0733b13d8a4beae3224c6c9e10354223  ./valid/unknown-type.fafm
a8000049a19f03bd0396ff806c210f9783349b48629287bd06e32d3066a7ed94  ./valid/unquoted-dates.fafm
878686152773f7416de509cc37f803eb222485b62c90a45a9db87ccef6d2e8b4  ./valid/voice.fafm
```
