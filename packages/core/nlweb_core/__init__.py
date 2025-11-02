"""NLWeb Core library."""

__version__ = "0.5.0"

import os


def init(config_path: str = None):
    """
    Initialize NLWeb with config file.

    Args:
        config_path: Path to config.yaml file. Defaults to:
                    1. NLWEB_CONFIG environment variable
                    2. ./config.yaml
                    3. ~/.nlweb/config.yaml
    """
    if config_path is None:
        # Try environment variable first
        config_path = os.getenv('NLWEB_CONFIG')

        # Try current directory
        if not config_path and os.path.exists('./config.yaml'):
            config_path = './config.yaml'

        # Try home directory
        if not config_path:
            home_config = os.path.expanduser('~/.nlweb/config.yaml')
            if os.path.exists(home_config):
                config_path = home_config

    if not config_path or not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            "Please provide config_path or set NLWEB_CONFIG environment variable."
        )

    # Set environment variable so config.py can find it
    config_dir = os.path.dirname(os.path.abspath(config_path))
    os.environ['NLWEB_CONFIG_DIR'] = config_dir

    # Reload config
    from nlweb_core.config import CONFIG
    CONFIG.__init__()
