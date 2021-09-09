# PR Review process for pf9-du 

## How to contribute

We are moving PR reviews for core services repositories (starting from pf9-du) to GitHub from Review Board (rbcommons).
This is facilitated under the hood by the prow tool from Kubernetes ecosystem.

Some of the advantages are:
1. Code, commit history, and review comments in one place
2. Chatops : Invoke commands related to code review from PR review discussion thread
3. Automerge for quicker turnaround

## Branching convention to follow:
Our branching strategy involves branch names like platform9-vX.X.X for releases, and atherton as the master branch
When we work on an issue, we need to follow this convention to trigger automerge into the correct branch on approval:
* Create a branch following the pattern `^private(\/)atherton(\/).+` (e.g. private/atherton/trilok/CORE-1038) when you want to merge work into atherton
* Create a branch following the pattern `^private(\/)platform9-v(\/).+` (e.g. private/platform9-v5.0/pshanbhag/CORE-xxxx)when you want to merge work into a release branch

## Merging using ChatOps
The command`/test automerge` will invoke merge into Atherton.
The commands (TBD for pf9-du) like `/test automerge_XXX` will result in merge into the corresponding release branch
A list of available commands that have been implemented will be available by running `/test ?`

### ChatOps commands for running smoke tests, building DU image etc.
* `/test run_smoketests` will run smoke tests on Atherton branch
* `/test build_du_image` will build DU image (using the pf9-du build in progress on Atherton branch)
** `/test build_du_image_5.0` will build DU image (using the pf9-du build in progress on platform9-v5.0 branch)

### Implementing additional tests/ ChatOps commands
* Add any builds and tests if required, by following [this guide](https://platform9.atlassian.net/wiki/spaces/~16005066/pages/1014169716/Onboard+a+github+repo+on+Prow+for+PR+automation) on the wiki.
* To modify the list of contributors (reviewers, approvers) edit the OWNERS file in root folder of repo source.
* To modify the pull request template, edit the file .github/PULL_REQUEST_TEMPLATE.md in root folder of repo source.
* To implement additional pre-submit actions, edit the file .prow.yaml in root folder of repo source.
* The file tooling/manifests/repos/pf9-du/config.yaml in [prow-infra](https://github.com/platform9/prow-infra) repo already contains definitions of ChatOps commands to run smoke tests, to build du image for Atherton branch or 5.0 release branch. Support for new branches can be added here with similar build_du_image_XX commands

