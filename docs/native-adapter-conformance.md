# Native adapter conformance

The native adapter conformance layer closes the gap between a deterministic compilation
plan and a concrete target-runtime adapter implementation.

## Preflight sequence

1. Fresh runtime authorization verifies qualification, trust, revocation and witness data.
2. Adapter identity properties must match the authorized profile, code and runtime hashes.
3. `NativeAdapterManifest` is parsed under the strict
   `aspenops.native-adapter-manifest/v1` schema.
4. Every operation and `adapter_key` required by the base compilation plan must be declared.
5. Topology readback, layout readback, save/reopen and failure-isolation capabilities are
   mandatory whenever the plan requires them.
6. Any conformance issue stops execution before the first compilation step.
7. The execution record binds both the manifest digest and the conformance-report digest.

## Failure isolation

The manifest accepts only two explicit contracts:

- `PRIVATE_CASE_DISCARD`: every attempt uses a private case that is discarded on failure;
- `TRANSACTIONAL_ROLLBACK`: the target adapter provides a tested rollback transaction.

An adapter cannot declare an unspecified or best-effort failure mode.

## Boundary

A conformant manifest is not vendor certification. It proves deterministic offline contract
coverage only. Aspen Plus/HYSYS object names, COM methods, ports, save/reopen fidelity,
solver behavior and engineering correctness require licensed Windows Golden Cases and
human engineering acceptance.
