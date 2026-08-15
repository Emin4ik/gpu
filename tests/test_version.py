from importlib.metadata import version

import pytest

from gputriage import __version__
from gputriage.cli import main


def test_package_version_matches_distribution_metadata():
    assert __version__ == "0.2.0a1"
    assert version("gputriage") == __version__


def test_cli_version_is_stable(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "gputriage 0.2.0a1"
