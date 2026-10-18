from hpikit.cli.testing import check_cli_starts


def test_cli_starts() -> None:
    # derived rather than spelled out, so that this file can be the same in every exporter
    # it has to stay directly in the package, e.g. emfitexport/, rather than in its tests/
    assert __spec__ is not None
    package = __spec__.parent
    check_cli_starts(f'{package}.export')
    check_cli_starts(f'{package}.dal')
