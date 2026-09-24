#!/bin/bash
# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

set -euo pipefail

REPO=${1:-https://github.com/Ramble-Project/ramble}
BRANCH=${2:-origin/develop}

rm -rf /workspace
git clone "$REPO" /workspace
cd /workspace
git checkout "$BRANCH"

. /opt/spack/share/spack/setup-env.sh
spack load py-pip

python -m pip install -r /workspace/requirements-pinned.txt

cat > /load_test_env.sh <<'EOF'
#!/bin/bash
. /opt/spack/share/spack/setup-env.sh
spack load py-pip
export SPACK_PYTHON=$(which python)
. /workspace/share/ramble/setup-env.sh
EOF

echo "To load test environment, run:"
echo ". /load_test_env.sh"

