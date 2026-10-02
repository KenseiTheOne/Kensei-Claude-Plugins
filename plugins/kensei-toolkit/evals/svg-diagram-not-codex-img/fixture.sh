#!/usr/bin/env bash
# Scaffold: a README whose "How it works" section is an ASCII diagram. No git: the case only
# checks which skill the request goes to.
set -euo pipefail
cat > README.md <<'MD'
# relay

A tiny job relay: a CLI queues jobs, a worker runs them and reports back.

## How it works

```
+--------+   HTTP POST /jobs   +---------+   Redis LPUSH   +--------+
|  CLI   | ------------------> |  API    | --------------> | Worker |
+--------+                     +---------+                 +--------+
     ^          status JSON         |                           |
     +------------------------------+ <------- result ----------+
```

The worker retries a failed job three times before it marks it dead.
MD
