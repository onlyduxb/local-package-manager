# lpm-py

## Description

A local package installer for python (to be used with locally hosted gitea).

## Setup

Run the install wizard `lpm setup`. You will be asked for a series of information such as:

- The gitea host (default is localhost:3000).
- Your gitea username.
- Gitea token.
- Github username (optional as lpm can be used to publish to github).
- Github token (skipped if the username is left blank).
- Pypi username (optional as lpm can be used to publish to pypi).
- Pypi token (skipped if the username is left blank).
- Storage location
- Default python interpreter.

To clear the current configuration run `lpm setup --clear`.

## Commands

Command prefix is `lpm` meaning 'local package manager'.

- `install [package name]`
- `update [package name]` update the specified package.
- `show [package name]` show information about the specified package.
- `publish [platform]` supported platforms are pypi and github will publish the local repository to the provided platform, any local dependencies used can be handled in four ways (found in the uploading packages section).
- `check --project [project path] --codes`, defaults to the current directory, shows if any packages cannot be found globally. Codes is false by default and shows status code response from pypi.

## Uploading packages

When you publish a local package to a public space such as pypi or github lpm will recursively search dependencies of your program to check if any dependencies are sourced locally. If any such dependencies are found there is four ways to deal with this problem.

1. Publish all to github and reference the dependencies as git links, lpm will handle changes to the dependencies so that they can be resolved easily making the process as seamless as possible, your local version will remain the same so local workflow is unaffected. This is the recommended default.
2. Publish dependencies to pypi first, any local packages will be uploaded to pypi.
3. Vendor, the source code of the local packages is copied directly into your codebase under the _vendor/ directory.
4. Abort and handle it manually.

## Author

Adam Worsnip (onlyduxb).
