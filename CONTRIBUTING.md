# Contributing to cp-liveset

Thanks for your interest in improving cp-liveset!

## Workflow: fork and pull request

This repository uses a **fork-and-pull-request** model. Outside contributors
can't push branches here directly — instead:

1. **Fork** the repository, then clone your fork.
2. Create a branch on your fork for your change.
3. Make the change, with tests where it makes sense.
4. Open a **pull request** against `main`.

`main` is protected: pull requests require review and a passing CI run
(lint, tests on Python 3.9–3.14, and a package build) before they can be merged.

## Development setup

```sh
python -m pip install -e ".[test,dev]"
```

## Before opening a pull request

- Run the tests: `pytest`
- Run the linter: `ruff check .`
- The live MIDI / hardware tests skip automatically when no CP88/CP73 is
  connected, so a normal `pytest` run is fine without a device.

## Working with the reverse-engineered formats

The SysEx Bulk Dump and `.X9*` (YSFC) container formats are partly
reverse-engineered; see
[`docs/implementation-notes.md`](docs/implementation-notes.md) for what was
verified against real hardware and how. If you have a CP88/CP73 and can confirm
behavior on the actual instrument, that kind of verification is especially
welcome — please mention it in your PR.

## Reporting bugs and security issues

- **Bugs / feature ideas:** open an [issue](https://github.com/michiel-dewilde/cp-liveset/issues).
- **Security vulnerabilities:** please report privately — see
  [`SECURITY.md`](SECURITY.md).
