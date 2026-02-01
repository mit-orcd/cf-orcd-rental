# Test Suite Maintenance Guide

This document contains prompts and procedures for maintaining, reviewing, and evolving the ORCD Rental Portal system test suite.

## Table of Contents

1. [Periodic Review Schedule](#periodic-review-schedule)
2. [Coverage Analysis Prompts](#coverage-analysis-prompts)
3. [Test Enhancement Prompts](#test-enhancement-prompts)
4. [Error Detection Prompts](#error-detection-prompts)
5. [Portal Evolution Prompts](#portal-evolution-prompts)
6. [Multi-Agent Review Prompts](#multi-agent-review-prompts)
7. [Maintenance Procedures](#maintenance-procedures)

---

## Periodic Review Schedule

### Weekly

- [ ] Review failed test reports from CI/CD
- [ ] Check for flaky tests (intermittent failures)
- [ ] Verify test execution times are acceptable

### Monthly

- [ ] Run coverage analysis prompt
- [ ] Review new portal features for test coverage
- [ ] Update YAML configurations if test data has become stale

### Quarterly

- [ ] Run comprehensive multi-agent review
- [ ] Update test dependencies
- [ ] Review and update this maintenance document

### On Portal Changes

- [ ] Run feature coverage analysis for changed files
- [ ] Add/modify/remove tests as needed
- [ ] Update YAML configurations for new entities

---

## Coverage Analysis Prompts

### Prompt 1: Full Portal Coverage Analysis

Use this prompt to analyze whether the test suite covers all portal features.

```
You are a QA engineer reviewing a test suite for the ORCD Rental Portal.

Please analyze the test suite located at:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/

And compare it against the portal's features in:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/coldfront_orcd_direct_charge/

Perform the following analysis:

1. **View Coverage**: List all views in views/ directory and identify which are tested
2. **URL Coverage**: List all URL patterns in urls.py and identify which are tested
3. **Model Coverage**: List all models in models.py and verify CRUD operations are tested
4. **Permission Coverage**: List all permissions and verify access control is tested
5. **Workflow Coverage**: Identify all workflows (state transitions) and verify they are tested
6. **API Coverage**: List all API endpoints and verify they are tested
7. **Edge Cases**: Identify potential edge cases that are not covered

For each gap identified, provide:
- Feature/endpoint not covered
- Recommended test case description
- Priority (High/Medium/Low)
- Estimated effort (Small/Medium/Large)

Output format:
## Coverage Summary
- Views: X/Y covered (Z%)
- URLs: X/Y covered (Z%)
- Models: X/Y covered (Z%)
- Permissions: X/Y covered (Z%)
- APIs: X/Y covered (Z%)

## Gaps Identified
| Priority | Feature | Description | Effort |
|----------|---------|-------------|--------|
| High | ... | ... | ... |

## Recommendations
1. ...
```

### Prompt 2: Specific Feature Coverage Check

Use when a specific feature has been modified.

```
You are a QA engineer verifying test coverage for a specific feature.

Feature to analyze: [FEATURE_NAME]
Files modified: [LIST_OF_FILES]

Review the test suite at:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/

Determine:

1. Which existing tests cover this feature?
2. Are the tests still valid after the modifications?
3. Do any tests need to be updated?
4. Are there new behaviors that need new tests?

For each finding, provide:
- Test file and test name
- Current status (Valid/Needs Update/Should Remove)
- Required changes (if any)
- New tests needed (if any)

Output a checklist of actions to take.
```

### Prompt 3: YAML Configuration Validation

Use to verify YAML test configurations are valid and complete.

```
You are a test configuration validator.

Review all YAML configuration files in:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/config/

Check for:

1. **Syntax Validity**: All YAML files parse correctly
2. **Schema Compliance**: All required fields are present
3. **Reference Integrity**: All cross-file references are valid (e.g., user IDs)
4. **Parameterization**: Variables are properly defined and used
5. **Test Data Quality**: Test data is realistic and comprehensive
6. **Date/Time Values**: Relative dates will work regardless of when tests run
7. **Completeness**: All entity types have sufficient test cases

Report:
- Errors that will cause test failures
- Warnings that may cause issues
- Suggestions for improvement
- Missing test scenarios
```

---

## Test Enhancement Prompts

### Prompt 4: Add Tests for New Feature

Use when a new feature is added to the portal.

```
You are implementing tests for a new feature in the ORCD Rental Portal.

New Feature: [FEATURE_DESCRIPTION]
Relevant Files:
- Views: [VIEW_FILES]
- Models: [MODEL_FILES]
- URLs: [URL_PATTERNS]
- Templates: [TEMPLATE_FILES]

Existing test suite is at:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/

Create a comprehensive test plan for this feature:

1. **YAML Configuration Updates**:
   - What new entries are needed in config files?
   - What new config file might be needed?

2. **Test Module Updates**:
   - Which existing module should contain these tests?
   - Or should a new module be created?
   - What is the correct position in the dependency chain?

3. **Test Cases**:
   - List all test cases needed (happy path, error cases, edge cases)
   - Include expected inputs and outputs
   - Specify user roles required for each test

4. **Dependencies**:
   - What existing tests must pass before these can run?
   - What data must exist in the system?

Provide:
- Complete YAML additions with proper formatting
- Test class/method signatures with docstrings
- Any utility functions needed
```

### Prompt 5: Improve Test Robustness

Use to make tests more reliable and maintainable.

```
You are a test reliability engineer reviewing the ORCD Rental Portal test suite.

Review the test modules at:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/modules/

Analyze each test module for:

1. **Flakiness Risks**:
   - Tests dependent on timing
   - Tests dependent on external services
   - Tests with race conditions
   - Tests with order dependencies

2. **Maintainability Issues**:
   - Hardcoded values that should be in YAML
   - Duplicated code across tests
   - Missing setup/teardown
   - Poor error messages

3. **Performance Issues**:
   - Slow tests that could be optimized
   - Unnecessary database operations
   - Missing test isolation

4. **Best Practices Violations**:
   - Tests that test too much
   - Tests that test too little
   - Missing assertions
   - Inappropriate use of mocks

For each issue found, provide:
- File and line number
- Problem description
- Recommended fix
- Code example (if applicable)
```

### Prompt 6: Generate Negative Test Cases

Use to ensure error handling is properly tested.

```
You are a security and reliability tester.

Review the ORCD Rental Portal at:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/coldfront_orcd_direct_charge/

For each view/endpoint, generate negative test cases:

1. **Authentication Failures**:
   - Unauthenticated access
   - Expired sessions
   - Invalid credentials

2. **Authorization Failures**:
   - Wrong role accessing protected resource
   - User accessing another user's data
   - Escalation attempts

3. **Validation Failures**:
   - Invalid input data
   - Missing required fields
   - Out-of-range values
   - Malformed data

4. **Business Logic Failures**:
   - Operations on wrong state (e.g., approve already approved)
   - Constraint violations
   - Dependency failures

5. **Concurrency Issues**:
   - Simultaneous conflicting operations
   - Race conditions

For each test case, provide:
- Test name
- Setup required
- Action to perform
- Expected error response
- YAML configuration if needed
```

---

## Error Detection Prompts

### Prompt 7: Find Test Bugs

Use to identify bugs in the test suite itself.

```
You are a code reviewer specializing in test code quality.

Review the test suite at:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/

Look for the following categories of bugs:

1. **Logic Errors**:
   - Incorrect assertions (testing wrong thing)
   - Inverted conditions
   - Off-by-one errors
   - Type mismatches

2. **Setup/Teardown Issues**:
   - Missing setup steps
   - Incomplete cleanup
   - State leakage between tests

3. **Assertion Errors**:
   - Missing assertions (test passes but doesn't verify anything)
   - Too broad assertions (always pass)
   - Wrong expected values

4. **API Misuse**:
   - Incorrect Django test client usage
   - Wrong HTTP methods
   - Missing authentication

5. **Configuration Errors**:
   - YAML parsing issues
   - Missing configuration values
   - Type errors in config

For each bug found:
- Location (file:line)
- Bug description
- Impact (what would this cause?)
- Fix recommendation
- Confidence level (Certain/Likely/Possible)
```

### Prompt 8: Validate Test Assertions

Use to ensure assertions are meaningful.

```
You are reviewing test assertions for correctness and completeness.

For each test in:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/modules/

Analyze assertions:

1. **Assertion Presence**:
   - Does every test have at least one assertion?
   - Are all critical outcomes verified?

2. **Assertion Correctness**:
   - Do assertions test the right thing?
   - Are expected values correct?

3. **Assertion Completeness**:
   - Are all side effects verified?
   - Are database changes verified?
   - Are response contents verified?

4. **Assertion Messages**:
   - Do assertions have helpful failure messages?
   - Can failures be easily diagnosed?

Report format:
| Test | Issue | Severity | Recommendation |
|------|-------|----------|----------------|
| ... | ... | ... | ... |
```

---

## Portal Evolution Prompts

### Prompt 9: Detect Stale Tests

Use when the portal has been updated significantly.

```
You are detecting tests that may have become stale or broken.

Compare the test suite at:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/

Against the current portal code at:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/coldfront_orcd_direct_charge/

Identify:

1. **Removed Features**:
   - Tests for views/models/endpoints that no longer exist
   - Tests using deprecated APIs

2. **Changed Signatures**:
   - Tests calling functions with wrong parameters
   - Tests expecting old response formats

3. **Changed Behavior**:
   - Tests with assertions that no longer match behavior
   - Tests for workflows that have changed

4. **Changed URLs**:
   - Tests using old URL patterns
   - Tests with hardcoded URLs that have moved

5. **Changed Permissions**:
   - Tests assuming old permission requirements
   - Tests using roles that have changed

For each stale test:
- Test location
- What changed in the portal
- Required test update
- Priority (tests that will fail vs. tests that will pass incorrectly)
```

### Prompt 10: Migration Planning

Use when major portal changes require test suite updates.

```
You are planning test suite migration for a major portal update.

Portal changes being made:
[DESCRIBE CHANGES]

Current test suite:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/

Create a migration plan:

1. **Impact Assessment**:
   - Which test modules are affected?
   - Which YAML configs need updates?
   - Which tests will break?

2. **Migration Steps** (in order):
   - Config file updates
   - Utility function updates
   - Test module updates
   - New tests to add
   - Tests to remove

3. **Validation Steps**:
   - How to verify migration is complete?
   - How to run partial test suite during migration?

4. **Rollback Plan**:
   - How to revert if migration fails?
   - What to preserve for comparison?

5. **Timeline Estimate**:
   - Effort for each step
   - Dependencies between steps
   - Parallel vs. sequential work
```

---

## Multi-Agent Review Prompts

### Prompt 11: Code Quality Review (General Purpose Agent)

```
You are a senior software engineer reviewing test code quality.

Review the test suite at:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/

Evaluate:

1. **Code Organization**:
   - Is the module structure logical?
   - Are files appropriately sized?
   - Is naming consistent?

2. **Code Style**:
   - Does code follow Python best practices?
   - Is code readable and self-documenting?
   - Are docstrings complete?

3. **Design Patterns**:
   - Are appropriate patterns used?
   - Is there unnecessary complexity?
   - Is the code DRY?

4. **Error Handling**:
   - Are exceptions handled appropriately?
   - Are error messages helpful?

5. **Documentation**:
   - Is TEST_WORKFLOW.md complete and accurate?
   - Are YAML configs well-documented?
   - Are complex tests explained?

Provide:
- Overall quality score (1-10)
- Top 5 strengths
- Top 5 areas for improvement
- Specific refactoring recommendations
```

### Prompt 12: Security Review (Security-Focused Agent)

```
You are a security engineer reviewing test coverage for security scenarios.

Review the portal at:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/coldfront_orcd_direct_charge/

And the test suite at:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/

Evaluate security test coverage:

1. **Authentication Tests**:
   - Login/logout flows
   - Session management
   - Password handling

2. **Authorization Tests**:
   - Permission checking
   - Role-based access
   - Object-level permissions

3. **Input Validation Tests**:
   - XSS prevention
   - SQL injection prevention
   - CSRF protection
   - File upload handling

4. **Data Protection Tests**:
   - Sensitive data handling
   - PII protection
   - Audit logging

5. **API Security Tests**:
   - Authentication requirements
   - Rate limiting
   - Input sanitization

For each security gap:
- Vulnerability type
- Risk level (Critical/High/Medium/Low)
- Test case to add
- Implementation notes
```

### Prompt 13: Performance Review (Performance-Focused Agent)

```
You are a performance engineer reviewing test suite efficiency.

Review:
/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/tests/system_tests/

Analyze:

1. **Test Execution Time**:
   - Which tests are slowest?
   - Which tests could be parallelized?
   - Which tests have unnecessary waits?

2. **Database Usage**:
   - Which tests make excessive DB queries?
   - Which tests could use fixtures more efficiently?
   - Which tests don't clean up properly?

3. **Resource Usage**:
   - Which tests consume excessive memory?
   - Which tests leave resources open?

4. **CI/CD Optimization**:
   - How can the test matrix be optimized?
   - Which tests should run on every commit?
   - Which tests can run less frequently?

5. **Test Data Efficiency**:
   - Is test data generation efficient?
   - Can test data be shared across tests?
   - Is there redundant data setup?

Recommendations:
- Specific optimizations with expected time savings
- Test grouping recommendations
- Caching opportunities
- Parallelization strategy
```

### Prompt 14: Cross-Agent Synthesis Review

```
You are synthesizing reviews from multiple specialized agents.

Previous reviews have been conducted:
1. Code Quality Review: [PASTE RESULTS]
2. Security Review: [PASTE RESULTS]
3. Performance Review: [PASTE RESULTS]

Synthesize findings:

1. **Prioritized Issue List**:
   - Combine all issues from all reviews
   - Remove duplicates
   - Prioritize by impact and effort

2. **Conflict Resolution**:
   - Identify conflicting recommendations
   - Propose resolutions

3. **Implementation Roadmap**:
   - Group related changes
   - Order by dependencies
   - Estimate total effort

4. **Quick Wins**:
   - What can be fixed immediately?
   - What provides most value for least effort?

5. **Long-term Improvements**:
   - What requires significant refactoring?
   - What should wait for next major version?

Output an actionable improvement plan with clear steps.
```

---

## Maintenance Procedures

### Adding a New Test

1. Determine which module the test belongs to
2. Add any required YAML configuration
3. Write the test following existing patterns
4. Run the test in isolation
5. Run the full suite to check for conflicts
6. Update TEST_WORKFLOW.md if adding new test categories

### Modifying Existing Tests

1. Understand why the test exists
2. Check for dependent tests
3. Make the change
4. Verify the test still catches the intended issues
5. Run related tests
6. Update documentation if behavior changed

### Removing Tests

1. Verify the tested functionality is actually removed
2. Check for tests that depend on this one
3. Remove YAML configuration if no longer needed
4. Update TEST_WORKFLOW.md
5. Document the removal in commit message

### Updating YAML Configuration

1. Validate YAML syntax before committing
2. Check all references to modified IDs
3. Run affected tests
4. Update related documentation

### CI/CD Updates

1. Test locally first
2. Update in a branch
3. Verify all matrix combinations pass
4. Monitor first few runs in production

---

## Prompt Templates for Common Tasks

### Template: Add Test for Bug Fix

```
I've fixed a bug in the ORCD Rental Portal:

Bug: [DESCRIPTION]
Fix: [WHAT WAS CHANGED]
Files: [LIST OF FILES]

Create a regression test to ensure this bug doesn't reoccur:

1. What module should contain this test?
2. What YAML configuration is needed?
3. Write the test case with:
   - Setup that creates the bug scenario
   - Action that triggered the bug
   - Assertion that verifies the fix
```

### Template: Investigate Test Failure

```
A test is failing in CI:

Test: [TEST_NAME]
Error: [ERROR_MESSAGE]
Last passing: [DATE/COMMIT]

Please investigate:

1. What does this test verify?
2. What changed since it last passed?
3. Is this a test bug or a portal bug?
4. What is the fix?
```

### Template: Review PR Test Changes

```
A PR modifies the test suite:

PR: [PR_NUMBER]
Changes: [SUMMARY]

Review the test changes:

1. Are the changes appropriate for the stated goal?
2. Do the tests follow existing patterns?
3. Is the YAML configuration correct?
4. Are there any issues with the implementation?
5. Are there missing tests?
```

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| [INITIAL_DATE] | 1.0 | Initial version |

---

## Related Documents

- [TEST_WORKFLOW.md](TEST_WORKFLOW.md) - Main test plan document
- [tests/README.md](../README.md) - General test documentation
- [CHANGELOG.md](../../developer_docs/CHANGELOG.md) - Portal changes that may affect tests
