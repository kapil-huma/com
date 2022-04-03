# Huma CLI

Full instructions for the CLI can be found [here](https://humahq.stoplight.io/docs/huma-platform-cli/ZG9jOjI1OTc3Mzc3-using-the-cli)

## Updating versioning

To update versioning do this:

1. Increment the version in huma/__init__.py
2. Increment the version in huma/lastest_cli_version.txt
3. Update the release notes around line 35 in huma/menu.py
4. In huma AWS account `Huma Main` go to S3 volume `huma-customer-frontend-assets` and upload and replace latest_cli_version.txt.  Be sure to set it to view public.

There is a video of these steps [here](https://drive.google.com/file/d/150U8UWAwWb5ZMLFZaY8L8ZmyPQ7tPYzz/view?usp=sharing)

## Release Info

The smoke tests now check if you have the latest version before running and exit if you do not.  This is due to the cli's nature that it doesn't work if huma-server is not released with the endpoints that the huma-cli requires. Also, sometimes it's advantageous to force users to use the latest version.

The software checks endpoint [this](https://huma-customer-frontend-assets.s3.amazonaws.com/latest_cli_version.txt) and compares it to huma/__init__.__version__.  Therefore to create a new update both of these items must be incremented and must match.  The endpoint is in Huma Main account in s3 for us-east-1.
