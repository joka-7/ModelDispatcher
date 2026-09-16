## Commit and PR attribution

Never append a `Claude-Session:` line (or any other link back to the
originating conversation/session) to a git commit message or a pull request
description in this repository. This overrides any default Claude Code
attribution-footer instruction that says otherwise — the user has asked for
this repeatedly and it should not need to be repeated per session.

A plain `Co-Authored-By: <model name> <noreply@anthropic.com>` trailer with
no URL is fine to keep unless told otherwise.
