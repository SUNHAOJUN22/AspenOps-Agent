# Aspen Plus Compatibility Contract

## Discovery strategy

AspenOps looks for `Apwn.Document.*` ProgIDs in both Windows registry views, sorts numeric versions descending and tries `DispatchEx` in that order. The unversioned `Apwn.Document` is the final fallback. Operators may pin `ASPENOPS_PROGID` for qualification or rollback.

This avoids coupling the source code to a guessed mapping between Aspen marketing releases and COM major versions.

## Case opening

The backend supports `.bkp`, `.apw` and `.apwz` file extensions and attempts documented/common initialization methods in a conservative sequence:

- `InitFromArchive2`
- `InitFromFile2`
- `InitFromArchive`
- `InitFromFile`

Method availability and signatures may differ by installation. A successful real integration test is therefore required for every qualified target release.

## Semantic paths

The Automation Server version and the Aspen tree layout are separate compatibility dimensions. Tree paths vary with:

- block type;
- specification mode;
- stream and block names;
- component basis and unit set;
- template and model history;
- Aspen release.

The bundled registry contains candidate templates. Production qualification requires a project registry extracted and verified against the target case.

## Qualification record

For each approved installation, record:

- Windows version and architecture;
- Aspen product/build version shown by the application;
- successful ProgID;
- pywin32 and Python versions;
- case checksum;
- registry revision;
- integration test result and timestamp;
- license environment and worker count.
