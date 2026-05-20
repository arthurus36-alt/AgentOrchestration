import sys
import pytest
from src.cli.main import cli
from unittest.mock import patch

def test_deploy_missing_manifest(capsys):
    test_args = ["main.py", "deploy", "non_existent_manifest.yml"]
    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as e:
            cli()
        
        assert e.value.code == 1
        captured = capsys.readouterr()
        assert "Error: Manifest file not found" in captured.err

def test_deploy_existing_manifest(tmp_path, capsys):
    manifest_file = tmp_path / "valid_manifest.yml"
    manifest_file.touch()
    
    test_args = ["main.py", "deploy", str(manifest_file)]
    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as e:
            cli()
        
        assert e.value.code == 0
        captured = capsys.readouterr()
        assert "Deploying agent from manifest" in captured.out
