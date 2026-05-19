import pytest
import sys
from src.cli.main import cli

def test_cli_valid_output_mode(capsys):
    # Valid mode should pass without SystemExit
    args = cli(["--output-mode", "json", "status"])
    assert args.output_mode == "json"
    
def test_cli_invalid_output_mode(capsys):
    # Invalid mode should trigger argparse error and exit
    with pytest.raises(SystemExit) as excinfo:
        cli(["--output-mode", "invalid_format", "status"])
    
    # Argparse exits with status 2 on error
    assert excinfo.value.code == 2
    
    captured = capsys.readouterr()
    assert "invalid choice: 'invalid_format'" in captured.err
