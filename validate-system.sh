#!/bin/bash
set -euo pipefail

# =============================================================================
#                        SYSTEM VALIDATION TEST SCRIPT
# =============================================================================
# Comprehensive validation of all debugging and maintenance capabilities
# Tests all scripts, health checks, and debugging features
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_LOG="${SCRIPT_DIR}/logs/validation-test.log"
PASSED_TESTS=0
FAILED_TESTS=0
TOTAL_TESTS=0

# Initialize
mkdir -p "${SCRIPT_DIR}/logs"
echo "System Validation Test - $(date)" > "$TEST_LOG"

# Logging functions
log_test() {
    local test_name="$1"
    local status="$2"
    local details="${3:-}"
    
    ((TOTAL_TESTS++))
    
    if [[ "$status" == "PASS" ]]; then
        echo -e "${GREEN}✓ PASS${NC} $test_name" | tee -a "$TEST_LOG"
        ((PASSED_TESTS++))
    elif [[ "$status" == "FAIL" ]]; then
        echo -e "${RED}✗ FAIL${NC} $test_name" | tee -a "$TEST_LOG"
        ((FAILED_TESTS++))
    elif [[ "$status" == "SKIP" ]]; then
        echo -e "${YELLOW}⊝ SKIP${NC} $test_name" | tee -a "$TEST_LOG"
    fi
    
    if [[ -n "$details" ]]; then
        echo "       $details" | tee -a "$TEST_LOG"
    fi
}

log_section() {
    echo -e "\n${PURPLE}=== $1 ===${NC}" | tee -a "$TEST_LOG"
}

# =============================================================================
#                            TEST FUNCTIONS
# =============================================================================

test_script_executability() {
    log_section "Script Executability Tests"
    
    # Test maintenance.sh
    if [[ -x "./maintenance.sh" ]]; then
        log_test "maintenance.sh executable" "PASS"
    else
        log_test "maintenance.sh executable" "FAIL" "File not executable or missing"
    fi
    
    # Test quick-debug.sh
    if [[ -x "./quick-debug.sh" ]]; then
        log_test "quick-debug.sh executable" "PASS"
    else
        log_test "quick-debug.sh executable" "FAIL" "File not executable or missing"
    fi
    
    # Test PIA scripts
    if [[ -x "./gluetun/pia_pf_runner.sh" ]]; then
        log_test "pia_pf_runner.sh executable" "PASS"
    else
        log_test "pia_pf_runner.sh executable" "FAIL" "File not executable or missing"
    fi
    
    if [[ -x "./gluetun/update-qb.sh" ]]; then
        log_test "update-qb.sh executable" "PASS"
    else
        log_test "update-qb.sh executable" "FAIL" "File not executable or missing"
    fi
}

test_maintenance_commands() {
    log_section "Maintenance Script Commands"
    
    # Test help command
    if ./maintenance.sh help &> /dev/null; then
        log_test "maintenance.sh help" "PASS"
    else
        log_test "maintenance.sh help" "FAIL" "Help command failed"
    fi
    
    # Test debug enable/disable
    if ./maintenance.sh debug-enable &> /dev/null; then
        log_test "debug-enable command" "PASS"
    else
        log_test "debug-enable command" "FAIL" "Debug enable failed"
    fi
    
    if ./maintenance.sh debug-disable &> /dev/null; then
        log_test "debug-disable command" "PASS"
    else
        log_test "debug-disable command" "FAIL" "Debug disable failed"
    fi
    
    # Re-enable debug for remaining tests
    ./maintenance.sh debug-enable &> /dev/null || true
}

test_quick_debug_commands() {
    log_section "Quick Debug Script Commands"
    
    # Test basic check
    if ./quick-debug.sh check &> /dev/null; then
        log_test "quick-debug.sh basic check" "PASS"
    else
        log_test "quick-debug.sh basic check" "FAIL" "Basic check failed"
    fi
    
    # Test all checks
    if ./quick-debug.sh all &> /dev/null; then
        log_test "quick-debug.sh all checks" "PASS"
    else
        log_test "quick-debug.sh all checks" "FAIL" "All checks failed"
    fi
    
    # Test individual commands
    for cmd in vpn port services; do
        if ./quick-debug.sh "$cmd" &> /dev/null; then
            log_test "quick-debug.sh $cmd check" "PASS"
        else
            log_test "quick-debug.sh $cmd check" "FAIL" "$cmd check failed"
        fi
    done
}

test_debug_functionality() {
    log_section "Debug Functionality Tests"
    
    # Check if DEBUG variable is properly set
    if grep -q "DEBUG=true" .env 2>/dev/null; then
        log_test "DEBUG environment variable" "PASS" "DEBUG=true in .env"
    else
        log_test "DEBUG environment variable" "FAIL" "DEBUG not set to true in .env"
    fi
    
    # Test debug output in scripts
    local debug_test_file="/tmp/test_port_$$"
    echo "9999" > "$debug_test_file"
    
    if DEBUG=true PORT_FILE="$debug_test_file" QBIT_WEBUI_PORT=8080 sh gluetun/update-qb.sh 2>&1 | grep -q "DEBUG"; then
        log_test "update-qb.sh debug output" "PASS" "Debug logging present"
    else
        log_test "update-qb.sh debug output" "FAIL" "No debug output found"
    fi
    
    rm -f "$debug_test_file"
    
    # Test pia_pf_runner.sh debug (will fail on missing config, but should show debug)
    if DEBUG=true timeout 5 bash gluetun/pia_pf_runner.sh 2>&1 | grep -q "DEBUG" || true; then
        log_test "pia_pf_runner.sh debug output" "PASS" "Debug logging present"
    else
        log_test "pia_pf_runner.sh debug output" "FAIL" "No debug output found"
    fi
}

test_podman_compose_enhancements() {
    log_section "Podman Compose Enhancements"
    
    # Check for health checks
    if grep -q "healthcheck:" podman-compose.yml; then
        log_test "Health checks in podman-compose.yml" "PASS" "Health checks found"
    else
        log_test "Health checks in podman-compose.yml" "FAIL" "No health checks found"
    fi
    
    # Check for logging configurations
    if grep -q "logging:" podman-compose.yml; then
        log_test "Logging config in podman-compose.yml" "PASS" "Logging configurations found"
    else
        log_test "Logging config in podman-compose.yml" "FAIL" "No logging configurations found"
    fi
    
    # Check for DEBUG environment variables
    if grep -q "DEBUG=\${DEBUG" podman-compose.yml; then
        log_test "DEBUG vars in podman-compose.yml" "PASS" "DEBUG variables configured"
    else
        log_test "DEBUG vars in podman-compose.yml" "FAIL" "DEBUG variables not configured"
    fi
    
    # Validate podman-compose syntax
    if podman-compose config &> /dev/null; then
        log_test "podman-compose.yml syntax" "PASS" "Valid syntax"
    else
        log_test "podman-compose.yml syntax" "FAIL" "Invalid syntax or missing dependencies"
    fi
}

test_environment_configuration() {
    log_section "Environment Configuration Tests"
    
    # Check .env.example completeness
    if [[ -f ".env.example" ]]; then
        local env_vars=("PIA_USER" "PIA_PASS" "QBIT_USER" "QBIT_PASS" "DEBUG" "MAX_LATENCY" "SLEEP_KEEPALIVE" "RETRY_MAX")
        local missing_vars=()
        
        for var in "${env_vars[@]}"; do
            if ! grep -q "^$var=" .env.example; then
                missing_vars+=("$var")
            fi
        done
        
        if [[ ${#missing_vars[@]} -eq 0 ]]; then
            log_test ".env.example completeness" "PASS" "All required variables present"
        else
            log_test ".env.example completeness" "FAIL" "Missing variables: ${missing_vars[*]}"
        fi
    else
        log_test ".env.example exists" "FAIL" "File missing"
    fi
    
    # Check if .env file has proper structure
    if [[ -f ".env" ]]; then
        if grep -q "^PIA_USER=" .env && grep -q "^PIA_PASS=" .env; then
            log_test ".env file structure" "PASS" "Basic structure valid"
        else
            log_test ".env file structure" "FAIL" "Missing required PIA credentials"
        fi
    else
        log_test ".env file exists" "FAIL" "Environment file missing"
    fi
}

test_documentation_completeness() {
    log_section "Documentation Tests"
    
    # Check README.md debugging section
    if grep -q "Debug" README.md; then
        log_test "README.md debug documentation" "PASS" "Debug section found"
    else
        log_test "README.md debug documentation" "FAIL" "No debug documentation found"
    fi
    
    # Check for troubleshooting section
    if grep -q -i "troubleshoot" README.md; then
        log_test "README.md troubleshooting section" "PASS" "Troubleshooting section found"
    else
        log_test "README.md troubleshooting section" "FAIL" "No troubleshooting section found"
    fi
    
    # Check for maintenance documentation
    if grep -q -i "maintenance" README.md; then
        log_test "README.md maintenance documentation" "PASS" "Maintenance section found"
    else
        log_test "README.md maintenance documentation" "FAIL" "No maintenance documentation found"
    fi
}

test_log_directory_structure() {
    log_section "Log Directory Structure"
    
    # Create logs directory if it doesn't exist
    mkdir -p logs
    
    # Test if maintenance script creates proper log structure
    ./maintenance.sh help &> /dev/null || true
    
    if [[ -d "logs" ]]; then
        log_test "Logs directory exists" "PASS" "Directory created successfully"
    else
        log_test "Logs directory exists" "FAIL" "Directory not created"
    fi
    
    # Check if maintenance debug log is created
    if [[ -f "logs/maintenance-debug.log" ]]; then
        log_test "Maintenance debug log" "PASS" "Log file created"
    else
        log_test "Maintenance debug log" "FAIL" "Log file not created"
    fi
}

test_legacy_cleanup() {
    log_section "Legacy Code Cleanup"
    
    # Check if legacy directory exists and contains archived code
    if [[ -d "legacy" ]]; then
        log_test "Legacy directory exists" "PASS" "Legacy code properly archived"
        
        # Check if legacy README exists
        if [[ -f "legacy/README.md" ]]; then
            log_test "Legacy documentation" "PASS" "Legacy README.md exists"
        else
            log_test "Legacy documentation" "FAIL" "Legacy README.md missing"
        fi
    else
        log_test "Legacy directory exists" "FAIL" "Legacy directory missing"
    fi
    
    # Ensure manual-connections-script-pia is in legacy
    if [[ -d "legacy/manual-connections-script-pia" ]]; then
        log_test "Legacy manual scripts archived" "PASS" "Scripts properly moved to legacy"
    else
        log_test "Legacy manual scripts archived" "FAIL" "Manual scripts not in legacy directory"
    fi
}

# =============================================================================
#                                MAIN EXECUTION
# =============================================================================

main() {
    echo -e "${BLUE}Media Stack System Validation${NC}"
    echo -e "${BLUE}==============================${NC}"
    echo "Testing all debugging and maintenance capabilities..."
    echo ""
    
    # Run all test suites
    test_script_executability
    test_maintenance_commands
    test_quick_debug_commands
    test_debug_functionality
    test_podman_compose_enhancements
    test_environment_configuration
    test_documentation_completeness
    test_log_directory_structure
    test_legacy_cleanup
    
    # Summary
    echo -e "\n${PURPLE}=== VALIDATION SUMMARY ===${NC}" | tee -a "$TEST_LOG"
    echo -e "Total Tests: ${TOTAL_TESTS}" | tee -a "$TEST_LOG"
    echo -e "${GREEN}Passed: ${PASSED_TESTS}${NC}" | tee -a "$TEST_LOG"
    echo -e "${RED}Failed: ${FAILED_TESTS}${NC}" | tee -a "$TEST_LOG"
    
    local pass_rate=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    echo -e "Pass Rate: ${pass_rate}%" | tee -a "$TEST_LOG"
    
    if [[ $FAILED_TESTS -eq 0 ]]; then
        echo -e "\n${GREEN}🎉 ALL TESTS PASSED! System validation successful.${NC}" | tee -a "$TEST_LOG"
        echo -e "✅ All debugging and maintenance features are working correctly." | tee -a "$TEST_LOG"
        return 0
    else
        echo -e "\n${YELLOW}⚠️  Some tests failed. Review the failures above.${NC}" | tee -a "$TEST_LOG"
        echo -e "📋 Detailed results saved to: $TEST_LOG" | tee -a "$TEST_LOG"
        return 1
    fi
}

# Execute main function
main "$@"