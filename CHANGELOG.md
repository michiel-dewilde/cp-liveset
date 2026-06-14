# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-14

Initial release.

### Added
- `LiveSetSound` / `LiveSetCollection` data model decoding every byte of the
  CP88/CP73 SysEx Bulk Dump (17 data blocks) into named, validated fields.
- Byte-exact JSON format (`cp88-cp73-liveset-v1`).
- Concise, hand-editable YAML format (`cp88-cp73-liveset-yaml-v1`): only
  non-default values, decoded into readable names/offsets.
- SysEx Bulk Dump I/O for `.mid` and `.syx` files, and live MIDI
  (`request_sound`/`send_sound`/`select_sound` and their group variants).
- YSFC container files: `.X9A` read; `.X9L` / `.X9P` / `.X9S` read and write
  (reverse-engineered from real device exports).
- `cp-liveset` command-line tool: `inspect`, `convert`, `select`,
  `list-midi-ports`, and `--version`.
- Fully typed public API (`py.typed`).

[1.0.0]: https://github.com/michiel-dewilde/cp-liveset/releases/tag/v1.0.0
