# Deterministic Delivery Bundle / 确定性交付包

`build_delivery_bundle.py` converts an exact AspenOps source revision into a reproducible software-handover package. It is a **software delivery** mechanism; it does not create or imply licensed Aspen Plus/HYSYS engineering certification.

`build_delivery_bundle.py` 将 AspenOps 的确定源码版本转换为可复现的软件移交包。它只完成**软件交付**，不会生成或暗示真实 Aspen Plus/HYSYS 商业工程资格。

## Build / 构建

```bash
rm -rf var/delivery
uv build

uv run python scripts/build_delivery_bundle.py \
  --source-sha "$(git rev-parse HEAD)" \
  --source-date-epoch 0 \
  --include-dist \
  --output-dir var/delivery
```

GitHub Actions or another immutable runner should pass the exact source identity rather than a branch name:

```bash
uv run python scripts/build_delivery_bundle.py \
  --source-sha "$GITHUB_SHA" \
  --source-date-epoch 0 \
  --include-dist \
  --output-dir var/ci/delivery-package
```

`source_sha` must be a 40-character lowercase hexadecimal Git SHA. `source_date_epoch` must be a non-negative integer.

## Produced artifacts / 生成产物

```text
aspenops-source-<sha12>.zip
aspenops-sbom-<sha12>.spdx.json
aspenops-evidence-index-<sha12>.json
aspenops-delivery-manifest-<sha12>.json
SHA256SUMS
aspenops-handover-<sha12>.zip
aspenops-handover-<sha12>.zip.sha256
wheel and source distribution, when --include-dist is used
```

Only `.whl` and `.tar.gz` distributions are admitted when `--include-dist` is used. Unrelated `.gz` files are ignored.

使用 `--include-dist` 时只接受 `.whl` 与 `.tar.gz` 分发产物；无关 `.gz` 文件不会进入交付包。

## Reproducibility / 可复现性

The source archive uses:

- lexicographically sorted members;
- fixed ZIP timestamp `1980-01-01T00:00:00Z`;
- normalized file mode `0644`;
- deterministic JSON serialization;
- `allow_nan=False`;
- exclusion of `.git`, virtual environments, caches, bytecode, `build/`, `dist/`, `var/`, and other transient trees.

源码归档采用排序成员、固定 ZIP 时间戳、规范权限和严格 JSON；缓存、虚拟环境、构建目录、`var/`、字节码和 VCS 内部文件不会进入源码包。

## Fail-closed path and size rules / 路径与大小门

The builder rejects:

- any symlink in the delivery source;
- absolute or `..` archive members;
- source files above the configured per-file limit;
- source trees above the configured total-size or file-count limits;
- an output path that is a regular file;
- a non-empty output directory;
- distribution artifacts above the size budget;
- qualification evidence that does not preserve `PENDING_REAL_ASPEN_CERTIFICATION`.

构建器对符号链接、路径逃逸、超大文件、超量源码、文件型输出路径、非空输出目录、超限分发产物以及伪造真实 Aspen 资格状态全部 fail closed。

The literal diagnostic `Symlink is not allowed` is intentionally retained as part of the acceptance contract.

## Integrity model / 完整性模型

For every payload artifact \(A_i\):

```math
h_i = SHA256(A_i)
```

The checksum list is:

```math
S = \operatorname{sort}\left\{(h_i,\operatorname{name}(A_i))\right\}
```

The handover archive is a deterministic function of the payload and normalized metadata:

```math
B = ZIP_{deterministic}(A_1,\ldots,A_n,Manifest,SHA256SUMS)
```

Its external checksum is:

```math
h_B = SHA256(B)
```

The manifest binds:

```text
source SHA
package name/version
real Aspen status
source archive identity
source-file count
artifact sizes
artifact SHA-256 values
reproducibility policy
qualification boundary
```

Manifest 绑定源码 SHA、包名/版本、真实 Aspen 状态、源码归档、源码文件数、产物大小、SHA-256、可复现性策略和资格边界。

## SBOM / 软件物料清单

The frozen `uv.lock` inventory is converted into `SPDX 2.3` JSON (`SPDX-2.3`). Dependency identity is recorded without inventing licence conclusions; unreviewed package licence fields remain `NOASSERTION`.

冻结的 `uv.lock` 会转换为 `SPDX 2.3` JSON。未经独立许可证审查时，许可证结论保持 `NOASSERTION`。

## Qualification evidence / 资格证据

The evidence index reads strict JSON only. Duplicate keys, `NaN`, `Infinity`, non-object roots, or a forged real-Aspen status are rejected.

The accepted external status is exactly:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

If `docs/DELIVERY_QUALIFICATION.json` exists, it can be included alongside the historical baseline; both must preserve the same external qualification boundary.

证据索引只读取严格 JSON。重复键、`NaN`、`Infinity`、非对象根以及伪造真实 Aspen 资格均会拒绝。

## Verification / 校验

```bash
cd var/delivery
sha256sum -c SHA256SUMS
sha256sum -c aspenops-handover-*.zip.sha256
```

Then verify the repository delivery surface:

```bash
python scripts/verify_delivery.py \
  --output var/ci/delivery-acceptance.json
```

If exact-tree qualification evidence has been produced:

```bash
python scripts/verify_delivery.py \
  --require-current-qualification \
  --output var/ci/delivery-acceptance-current.json
```

A deterministic bundle proves that source, software artifacts, documents, tests, and evidence are bound to one declared source identity. It does **not** prove that an unprovided licensed solver, customer model, property method, hardware environment, or engineering tolerance is correct.

确定性交付包证明的是软件与证据的绑定关系，不证明未提供的商业求解器、客户模型、物性方法、硬件环境或工程容差正确。
