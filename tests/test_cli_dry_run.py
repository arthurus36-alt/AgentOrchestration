import sys
import pytest
from src.cli.main import cli
from unittest.mock import patch

def test_deploy_dry_run(tmp_path, capsys):
    manifest_file = tmp_path / "valid_manifest.yml"
    manifest_file.touch()
    
    test_args = ["main.py", "deploy", str(manifest_file), "--dry-run"]
    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as e:
            cli()
        
        assert e.value.code == 0
        captured = capsys.readouterr()
        assert "Dry run: Manifest" in captured.out
        assert "Deploying agent from manifest" not in captured.out
