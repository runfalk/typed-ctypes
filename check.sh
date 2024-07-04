#!/bin/bash
set -euo pipefail

# Set current working directory to the repository root, so this script can be
# called from anywhere
SCRIPT_PATH=$(realpath "$0")
ROOT_DIR="$(dirname "${SCRIPT_PATH}")"
cd "$ROOT_DIR"

help_msg() {
    cat <<EOF
Usage: $0 [OPTIONS]

  Runs static analysis for this repository.

Options:
  -h, --help  Show this help and exit
  --fix       Apply fixes for applicable checkers
EOF
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            help_msg
            exit 0
            ;;
        --fix)
            APPLY_FIXES="1"
            ;;
        *)
            echo "Unknown argument '$1', run $0 --help for usage instructions."
            exit 1
            ;;
    esac
    # Shift the current argument off the stack
    shift
done

# By default we don't aply any fixes
APPLY_FIXES="${APPLY_FIXES:-0}"

# The default value is the 0 exit code
exit_status=0

# Force color output for ruff
export CLICOLOR_FORCE=1

# Force color output for pyright
export FORCE_COLOR=2

# Disable version check warning for pyright
export PYRIGHT_PYTHON_IGNORE_WARNINGS=1

# ANSI codes
ANSI_RESET="\e[0m"
ANSI_BOLD="\e[1m"
ANSI_UNDERLINE="\e[4m"
ANSI_FG_GREEN="\e[32m"
ANSI_FG_YELLOW="\e[33m"
ANSI_FG_RED="\e[31m"
ANSI_ERASE_UNTIL_EOL="\e[0K"

NEXT_CMD_ID="1"

run_cmd() {
    local cmd="$@"
    local exit_status="0"

    # This escape section allows us to collapse the output of jobs and track time for
    # each step
    section_id="cmd-$((NEXT_CMD_ID++))"
    echo -ne "${ANSI_ERASE_UNTIL_EOL}section_start:`date +%s`:${section_id}\r${ANSI_ERASE_UNTIL_EOL}"
    echo -e "Running '${cmd}'"
    $cmd 2>&1|sed "s/^/    /" || exit_status=$?
    echo -e "${ANSI_ERASE_UNTIL_EOL}section_end:`date +%s`:${section_id}\r${ANSI_ERASE_UNTIL_EOL}"

    if [ $exit_status -eq 0 ]; then
        echo -e "    Finished ${ANSI_BOLD}$cmd ${ANSI_FG_GREEN}(OK)${ANSI_RESET}"
    else
        echo -e "    Finished ${ANSI_BOLD}$cmd ${ANSI_FG_RED}(FAILED)${ANSI_RESET}"
    fi
    return $exit_status
}

ruff_format_cmd="poetry run ruff format"
if [[ $APPLY_FIXES -eq 0 ]]; then
    ruff_format_cmd="$ruff_format_cmd --check"
fi
run_cmd $ruff_format_cmd || exit_status=1

ruff_lint_cmd="poetry run ruff check --output-format full"
if [[ $APPLY_FIXES -eq 1 ]]; then
    ruff_lint_cmd="$ruff_lint_cmd --fix"
fi
run_cmd $ruff_lint_cmd || exit_status=1

pyright_cmd="poetry run pyright"
run_cmd $pyright_cmd || exit_status=1

pyright_cmd="poetry run mypy typed_ctypes.py test_typed_ctypes.py"
run_cmd $pyright_cmd || exit_status=1

poetry_lock_cmd="poetry lock --no-update"
if [[ $APPLY_FIXES -eq 0 ]]; then
    poetry_lock_cmd="poetry check --lock"
fi
run_cmd $poetry_lock_cmd || exit_status=1

exit $exit_status
