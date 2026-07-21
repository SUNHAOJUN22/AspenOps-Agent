# AspenOps single-main audit

- Status: **PASS**
- Source main SHA: `ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2`
- Package: `aspenops-nexus 2.0.0`
- Remaining branch refs: `1` (`main` only)
- Deleted in the final audit: `2`
- Closed transient PRs: `#20`, `#21`
- Open pull requests after cleanup: `0`
- Linux production CI: **PASS**
- Windows control-plane gate: **PASS**
- Python 3.12 tests: **563 passed**
- Branch-aware combined coverage: **94.97%**
- Coverage floor: **94.5%**
- Build / wheel / MCP / benchmark policy: **PASS**
- Authoritative workflows: `ci.yml`, `generate-performance-evidence.yml`, `licensed-aspen-certification.yml`, `windows-control-plane.yml`
- Removed superseded workflows: `final-main-pr-transaction.yml`, `windows-aspen-certification.yml`
- Real Aspen status: `PENDING_REAL_ASPEN_CERTIFICATION`

Public CI verifies the control plane and does not claim licensed physical Aspen certification. Historical branch tips remain recoverable through archive tags, but they are no longer active development branches.
