# Development guide

## Releases

To release a new version of this project follow these steps:

1. `git fetch && git checkout -B release/candidate origin/main`
1. Replace the “Upcoming” heading of the changelog with the new version number
   and date of release.
1. Update the version in `pyproject.toml`
1. Run `uv lock`
1. Commit the changes with the commit message “release: vX.Y.Z”
1. Push the changes `git push origin` and wait for the build to pass.
1. Build the package: `rm -rf dist && uv build`
1. Publish the package: `uv publish`
1. Merge release candidate into main branch
