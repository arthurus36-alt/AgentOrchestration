from unittest.mock import patch
from src.cli.main import cli



class TestCLI:
    @patch("sys.argv", ["cli", "deploy", "non_existent_manifest.yaml"])
    @patch("os.path.exists", return_value=False)
    @patch("sys.exit")
    @patch("builtins.print")
    def test_deploy_missing_manifest(self, mock_print, mock_exit, mock_exists):
        cli()
        mock_exists.assert_called_once_with("non_existent_manifest.yaml")
        mock_print.assert_called_once_with("Error: Manifest file 'non_existent_manifest.yaml' does not exist.")
        mock_exit.assert_called_once_with(1)

    @patch("sys.argv", ["cli", "deploy", "valid_manifest.yaml"])
    @patch("os.path.exists", return_value=True)
    @patch("builtins.print")
    def test_deploy_valid_manifest(self, mock_print, mock_exists):
        cli()
        mock_exists.assert_called_once_with("valid_manifest.yaml")
        mock_print.assert_called_with("Deploying agent from manifest: valid_manifest.yaml")
