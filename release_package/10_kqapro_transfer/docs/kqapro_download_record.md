# KQA Pro Download Record

Date: 2026-06-23

Source: OpenDataLab `OpenDataLab/KQA_Pro`

Downloaded archive:

- `data.zip` (local path is user-defined and is not part of this repository)
- SHA256: `E009593140D3971389821B7DB0C55E9A44CF5D6D3506AC30E97945BEA5B5D2E9`
- Size: `24,797,515` bytes

Recommended extraction directory:

- `data/kqapro/`

Extracted files:

| File | Records / KG Size | SHA256 |
|---|---:|---|
| `kb.json` | 794 concepts; 16,960 entities | `04DA7408320C5CB7023C44372CCE32846D56D369D8865D2E61A18C3956661A7C` |
| `train.json` | 94,376 questions | `E9FBE4C1CDF207AAC83AE0D5E4A1A53A9965A2B13B403DE699CA6D5DAE6E4510` |
| `val.json` | 11,797 questions | `B4AED6AB3D7AD071722064FE3BB02BC028CFBEB15DA5F7115D57A1E2D198F3BB` |
| `test.json` | 11,797 questions | `B2142ED6124AE525B7D7FD8D1EDB338C1B025751AC0167FF1498608111911822` |

Note:

The OpenXLab CLI `dataset download --source-path /raw/data.zip` was blocked by an Aliyun 405 page when using the legacy `/datasets/resolve/.../raw/data.zip` path. The working method uses the web frontend API:

`POST https://openxlab.org.cn/datasets/api/v3/datasets/OpenDataLab,KQA_Pro/r/main`

with JSON body:

```json
{"path":"raw/data.zip","preview":false}
```

The original download helper was used only during data acquisition and is not
required for reproduction. Obtain KQA Pro from its official source and verify
the extracted files with the hashes above.
