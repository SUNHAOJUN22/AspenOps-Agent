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

GitHub Actions uses the immutable `GITHUB_SHA`:

```bash
uv run python scripts/build_delivery_bundle.py \
  --source-sha "$GITHUB_SHA" \
  --source-date-epoch 0 \
  --include-dist \
  --output-dir var/ci/delivery-package
```

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

The source archive uses sorted members, a fixed ZIP timestamp and normalized file mode. Cache directories, virtual environments, build outputs, `var/`, bytecode and VCS internals are excluded. Symlinks, unsafe paths, excessive file counts and excessive payload sizes fail closed.

源码归档采用确定顺序、固定 ZIP 时间戳和规范文件权限；排除缓存、虚拟环境、构建目录、`var/`、字节码和版本控制内部文件。符号链接、路径逃逸、超量文件和超大载荷均会拒绝。

## Integrity model / 完整性模型

For every payload artifact \(A_i\):

```math
h_i = SHA256(A_i)
```

The checksum list is:

```math
S = \operatorname{sort}\left\{(h_i,\operatorname{name}(A_i))\right\}
```

The handover archive is a deterministic function of the payload set and normalized metadata:

```math
B = ZIP_{deterministic}(A_1,\ldots,A_n,Manifest,SHA256SUMS)
```

Its external checksum is:

```math
h_B = SHA256(B)
```

The manifest binds the source SHA, package name/version, qualification boundary, source-file count, artifact sizes and artifact SHA-256 values. JSON serialization uses sorted keys and `allow_nan=False`.

Manifest 绑定源码 SHA、包名/版本、资格边界、源码文件数、产物大小和 SHA-256。所有 JSON 使用排序键并禁止 `NaN/Infinity`。

## SBOM / 软件物料清单

The builder converts the frozen `uv.lock` package inventory into SPDX 2.3 JSON. The SBOM describes dependency identity only; licence conclusions remain `NOASSERTION` unless separately reviewed.

构建器将冻结的 `uv.lock` 依赖清单转换为 SPDX 2.3 JSON。SBOM 只描述依赖身份；未经独立许可证审查时，许可证结论保持 `NOASSERTION`。

## Evidence boundary / 证据边界

The evidence index records strict-JSON qualification files and their byte size and SHA-256. The following status remains explicit until real external evidence exists:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

A delivery bundle can prove that the software, documentation, tests and artifacts are bound to one source revision. It cannot prove that an unprovided licensed solver, customer model, property method, hardware environment or engineering tolerance is correct.

交付包可以证明软件、文档、测试和产物绑定到同一源码版本；它不能证明未提供的商业求解器、客户模型、物性方法、硬件环境或工程容差正确。

## Verification / 校验

```bash
sha256sum -c var/delivery/SHA256SUMS
sha256sum -c var/delivery/aspenops-handover-*.zip.sha256
python scripts/verify_delivery.py --output var/ci/delivery-acceptance.json
uv run pytest tests/test_delivery_bundle.py tests/test_delivery_acceptance.py
```
