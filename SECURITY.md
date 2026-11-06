# Security Policy

This tool runs locally, collects no data, sends nothing anywhere, and needs no API key or secret. It only reads the tag names you name (or the local tags of the repo you run it in), and it never creates, moves, or deletes a tag, and never changes a file. It writes nothing except the report on standard output (and usage errors on standard error).

If you find a case where the tool changes a tag or a file, or reports a pass for a tag that does not follow vMAJOR.MINOR.PATCH, please open an issue describing the exact commands and input. Do not include any real secret in the report.
