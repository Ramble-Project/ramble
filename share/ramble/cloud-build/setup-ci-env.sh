#!/bin/bash
# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

# Save caller's errexit state and disable during environment setup
_ramble_ci_errexit=0
case $- in
  *e*) _ramble_ci_errexit=1; set +e ;;
esac

cd /workspace

# Ensure develop branch exists for comparison in PR builds
if ! git rev-parse --verify develop >/dev/null 2>&1; then
  git branch develop origin/develop 2>/dev/null || true
fi

# Pre-seed cache from container image if available to avoid cloning over network.
# This must happen BEFORE sourcing setup-env.sh, as setup-env.sh invokes spack.
if [ -d /root/.spack ]; then
  mkdir -p "$HOME/.spack"
  cp -rn /root/.spack/. "$HOME/.spack/" 2>/dev/null || true
fi

# Initialize Spack and load py-pip with retries against transient git/network failures
spack_loaded=0
for attempt in 1 2 3; do
  unset _sp_initializing
  if . /opt/spack/share/spack/setup-env.sh && spack load py-pip ^python; then
    spack_loaded=1
    break
  fi
  echo "WARNING: Spack initialization / 'spack load py-pip ^python' failed on attempt $attempt of 3."
  rm -rf "$HOME/.spack/package_repos"
  sleep 5
done

if [ $spack_loaded -eq 0 ] || ! command -v pip >/dev/null 2>&1; then
  echo "======================================================================"
  echo "FATAL: Infrastructure Failure - Failed to initialize Spack environment."
  echo "'spack load py-pip ^python' failed after 3 attempts."
  echo "This is caused by transient external network issues reaching GitHub"
  echo "(https://github.com/spack/spack-packages.git)."
  echo "======================================================================"
  exit 1
fi

if ! pip install -r /workspace/requirements-pinned.txt; then
  echo "FATAL: Failed to install pinned requirements via pip."
  exit 1
fi

export SPACK_PYTHON=$(which python3)

unset _rmb_initializing
. /workspace/share/ramble/setup-env.sh

echo "Spack version is $(spack --version)"
echo "Python version is $(python3 --version)"

# Restore caller's errexit state
if [ $_ramble_ci_errexit -eq 1 ]; then
  set -e
fi
unset _ramble_ci_errexit
