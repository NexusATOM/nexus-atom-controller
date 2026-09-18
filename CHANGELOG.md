# Changelog

## Unreleased

- Journal experiment sealing before atomically publishing metadata, allowing restart to complete interrupted file/ledger commits without repeating execution.
- Persist each terminal task event and its budget checkpoint in one SQLite transaction.
- Retain recorded results, artifact hashes and partial logs when recovering interrupted experiments. Report changed/missing task evidence and never promote an unfinished attempt.
- Verify the ledger payload and metadata file against the same checksum. Keep existing completed v0.1.0 stores readable without rewriting them.

## 0.1.0

Initial multi-repository Nexus ATOM implementation. See README for implemented contracts, verification and production integration boundaries.

## Unreleased experiment reports

- Automatically generate Markdown summaries, evaluation JSON, and metric CSV for
  new attempts and interrupted recovery, then include them in the sealed manifest.
- Preserve existing sealed experiments without rewriting reports on resume.
