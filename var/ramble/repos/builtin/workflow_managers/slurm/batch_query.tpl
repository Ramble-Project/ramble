#!/bin/bash

. {batch_helpers}

job_id=$(get_job_id) || exit 0

# Set up the status_map mapping between
# sacct/squeue status to ramble counterpart
{declare_status_map}

sacct_out=$(sacct -j "${job_id}" -o 'state,nodelist,start,end,elapsedraw,exitcode' -X -P -n 2>/dev/null | tail -n1)
IFS='|' read -r sacct_status job_nodes job_start job_end job_elapsed_seconds job_exit_code _ <<< "$sacct_out"

sacct_state="${sacct_status%% *}"
case "$sacct_state:${job_end:-Unknown}" in
    *:Unknown|*:None|*:N/A) status=$(squeue -h -o "%t" -j "${job_id}" 2>/dev/null) ;;
    COMPLETED:*|CD:*|FAILED:*|F:*|CANCELLED*:*|CA:*|TIMEOUT:*|TO:*) status="$sacct_state" ;;
    *) status=$(squeue -h -o "%t" -j "${job_id}" 2>/dev/null) ;;
esac
status="${status:-$sacct_state}"
if [ -n "$status" ] && [ -v status_map["$status"] ]; then
    status=${status_map["$status"]}
fi

# Avoid clobbering existing .slurm_job_info if neither squeue nor sacct returned data
if [ -z "$status" ] && [ -z "$sacct_out" ]; then
    exit 0
fi

saved="{experiment_run_dir}/.slurm_job_info"
tmp_saved="${saved}.tmp"

{
    echo "job {job_name} with id ${job_id} has status: $status"
    echo "job info:"
    echo "  job_id: ${job_id}"
    echo "  job_name: {job_name}"
    echo "  job_status: $status"
    echo "  job_nodes: ${job_nodes}"
    echo "  job_start: ${job_start}"
    echo "  job_end: ${job_end}"
    echo "  job_elapsed_seconds: ${job_elapsed_seconds}"
    echo "  job_exit_code: ${job_exit_code}"
} | tee "$tmp_saved"

# Only update the actual file if the content has changed to preserve its mtime,
# this is to avoid unnecessary analyze cache invalidations.
if [ -f "$saved" ] && cmp -s "$saved" "$tmp_saved"; then
    rm "$tmp_saved"
else
    mv "$tmp_saved" "$saved"
fi
