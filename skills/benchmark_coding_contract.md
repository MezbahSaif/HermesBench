---
name: benchmark_coding_contract
description: Mandatory rules for code generation, module imports, and file persistence in benchmark environments.
---

# Benchmark Execution Rules

When completing coding and refactoring tasks in this environment, you MUST
follow these guidelines:

## 1. File Modification Rule

- Always directly modify or overwrite the target files specified in the
  prompt inside the `work/` directory.
- Running temporary verification scripts via terminal is permitted, but the
  FINAL solution MUST be written directly to the target source file.
- Unsaved edits in interactive buffers or temporary files will result in a
  ZERO score.

## 2. Code Block Formatting

- All executable Python code MUST be wrapped in standard markdown code
  fences:

```python
# Your code here
```

- Never output plain conversational summaries or raw markdown tables in place
  of requested code files.

## 3. Module Import Contract for Test Suites

- When writing unit tests for provided modules, always import the module
  under test using the dynamic handle `mod` as specified by the task prompt:

```python
import mod
```

- Do NOT use relative path hacks or hardcoded alternative names like
  `import good as correct_module` or `from good import Cart`.
