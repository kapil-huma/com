import click
import requests
import huma.__init__ as i
import os

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\x1b[0;32m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    CLEAR = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def init_extensions(f):
    validate_version()
    #recent_changes()
    return f

def validate_version():
    # Custom init code is here
    if not check_latest_cli_version():
        click.echo(click.style("There is a new version of the CLI.  The CLI is now coupled to version of the environment that is released.", fg='red'))
        click.echo(click.style("Please update with `pip uninstall huma-sdk -y && pip install 'huma@git+ssh://github.com/humahq/huma-cli.git' --upgrade`", fg='green'))
        exit(0)

def check_latest_cli_version() -> bool:
    import huma.__init__ as i
    version = i.__version__
    try:
        if not os.environ.get("AWS_BATCH_JOB_ID"):
            request = requests.get("https://huma-customer-frontend-assets.s3.amazonaws.com/latest_cli_version.txt")
            version_text = request.text
            return version == version_text
        return True
    except Exception as e:
        return False
