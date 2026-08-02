# HermesBench — Software Engineering Task Overview (Rounds 1–5)

The benchmark runs 5 rounds × 14 tasks × 2 arms = **140 agent executions**. Each round runs the same 14-task battery again; the **only** difference between rounds is what the agent remembers (treatment arm) vs. forgets (control arm).

## The 7 task families

| Family | What the agent must do |
|---|---|
| `bug_fix` | Find and fix a seeded bug in a working module (`main.py`). Graded by hidden `check()` assertions running against the fixed module. |
| `implement_function` | Implement a well-known algorithm from a stub (`solution.py` with `raise NotImplementedError`). Graded by hidden `check()` assertions. |
| `refactor` | Clean up working but ugly code (`ugly.py`): remove `global`, deduplicate, keep the same API. Graded by hidden `check()` assertions (behavior must be unchanged). |
| `write_tests` | Write unit tests that pass on `good.py` AND catch the seeded bug in `buggy.py`. Graded by running the tests against both modules in a subprocess. |
| `fastapi_setup` | Build a FastAPI app (`app.py`) from a README spec. Graded by required elements present in the files. |
| `docker_configure` | Write `Dockerfile` + `docker-compose.yml` for a given project. Graded by required directives present in the files. |
| `cli_tool` | Build a CLI tool (`cli.py`) matching a README spec exactly. Graded by RUNNING the CLI and comparing stdout line-by-line. |

Each task is fully self-contained: the prompt the agent receives **is** the whole task description shown in the second section of this file.

## Rounds at a glance (task_ids per round)

### Round 1
| # | Task ID | Family |
|---|---|---|
| 1 | `bug_fix_text_wrong_regex` | bug_fix |
| 2 | `bug_fix_text_offbyone` | bug_fix |
| 3 | `cli_filter` | cli_tool |
| 4 | `cli_json_pretty` | cli_tool |
| 5 | `docker_streamlit_dashboard` | docker_configure |
| 6 | `docker_cron_worker` | docker_configure |
| 7 | `fastapi_catalog` | fastapi_setup |
| 8 | `fastapi_todos` | fastapi_setup |
| 9 | `implement_knapsack` | implement_function |
| 10 | `implement_lru_cache` | implement_function |
| 11 | `refactor_invoice` | refactor |
| 12 | `refactor_config` | refactor |
| 13 | `write_tests_temperature` | write_tests |
| 14 | `write_tests_stats` | write_tests |

### Round 2
| # | Task ID | Family |
|---|---|---|
| 1 | `bug_fix_scheduling_offbyone` | bug_fix |
| 2 | `bug_fix_finance_wrong_accum` | bug_fix |
| 3 | `cli_sales` | cli_tool |
| 4 | `cli_word_freq` | cli_tool |
| 5 | `docker_flask_api` | docker_configure |
| 6 | `docker_streamlit_dashboard` | docker_configure |
| 7 | `fastapi_orders` | fastapi_setup |
| 8 | `fastapi_todos` | fastapi_setup |
| 9 | `implement_flatten_json` | implement_function |
| 10 | `implement_merge_intervals` | implement_function |
| 11 | `refactor_logs` | refactor |
| 12 | `refactor_config` | refactor |
| 13 | `write_tests_urlparser` | write_tests |
| 14 | `write_tests_banking` | write_tests |

### Round 3
| # | Task ID | Family |
|---|---|---|
| 1 | `bug_fix_finance_wrong_compare` | bug_fix |
| 2 | `bug_fix_finance_offbyone` | bug_fix |
| 3 | `cli_filter` | cli_tool |
| 4 | `cli_json_pretty` | cli_tool |
| 5 | `docker_cron_worker` | docker_configure |
| 6 | `docker_flask_api` | docker_configure |
| 7 | `fastapi_catalog` | fastapi_setup |
| 8 | `fastapi_orders` | fastapi_setup |
| 9 | `implement_max_profit` | implement_function |
| 10 | `implement_edit_distance` | implement_function |
| 11 | `refactor_invoice` | refactor |
| 12 | `refactor_logs` | refactor |
| 13 | `write_tests_cart` | write_tests |
| 14 | `write_tests_temperature` | write_tests |

### Round 4
| # | Task ID | Family |
|---|---|---|
| 1 | `bug_fix_scheduling_wrong_key` | bug_fix |
| 2 | `bug_fix_finance_bad_default` | bug_fix |
| 3 | `cli_word_freq` | cli_tool |
| 4 | `cli_sales` | cli_tool |
| 5 | `docker_cron_worker` | docker_configure |
| 6 | `docker_streamlit_dashboard` | docker_configure |
| 7 | `fastapi_todos` | fastapi_setup |
| 8 | `fastapi_orders` | fastapi_setup |
| 9 | `implement_max_profit` | implement_function |
| 10 | `implement_edit_distance` | implement_function |
| 11 | `refactor_config` | refactor |
| 12 | `refactor_logs` | refactor |
| 13 | `write_tests_temperature` | write_tests |
| 14 | `write_tests_stats` | write_tests |

### Round 5
| # | Task ID | Family |
|---|---|---|
| 1 | `bug_fix_scheduling_wrong_compare` | bug_fix |
| 2 | `bug_fix_text_wrong_compare` | bug_fix |
| 3 | `cli_sales` | cli_tool |
| 4 | `cli_word_freq` | cli_tool |
| 5 | `docker_flask_api` | docker_configure |
| 6 | `docker_cron_worker` | docker_configure |
| 7 | `fastapi_orders` | fastapi_setup |
| 8 | `fastapi_catalog` | fastapi_setup |
| 9 | `implement_max_profit` | implement_function |
| 10 | `implement_flatten_json` | implement_function |
| 11 | `refactor_invoice` | refactor |
| 12 | `refactor_config` | refactor |
| 13 | `write_tests_temperature` | write_tests |
| 14 | `write_tests_stats` | write_tests |

## Full task prompts (verbatim, one per unique task)

Repeated task_ids in later rounds reuse the **exact same prompt** — the full text is shown once here.

### bug_fix (10 unique tasks)

#### `bug_fix_finance_bad_default` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: main.py.

TASK: The module `main.py` contains a software defect (invoice total computation). Find the bug and fix it IN PLACE in main.py (invoice parsing, subtotal, bulk discount, tax). Do not change the module's public API, do not add new dependencies, do not weaken behavior.
Files in the workdir are yours to edit.
Difficulty: medium (a ~50-line module with a seeded logic bug).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the fixed module passes all of the project's unit tests (run them if you can).
````

#### `bug_fix_finance_offbyone` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: main.py.

TASK: The module `main.py` contains a software defect (invoice total computation). Find the bug and fix it IN PLACE in main.py (invoice parsing, subtotal, bulk discount, tax). Do not change the module's public API, do not add new dependencies, do not weaken behavior.
Files in the workdir are yours to edit.
Difficulty: medium (a ~50-line module with a seeded logic bug).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the fixed module passes all of the project's unit tests (run them if you can).
````

#### `bug_fix_finance_wrong_accum` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: main.py.

TASK: The module `main.py` contains a software defect (invoice total computation). Find the bug and fix it IN PLACE in main.py (invoice parsing, subtotal, bulk discount, tax). Do not change the module's public API, do not add new dependencies, do not weaken behavior.
Files in the workdir are yours to edit.
Difficulty: medium (a ~50-line module with a seeded logic bug).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the fixed module passes all of the project's unit tests (run them if you can).
````

#### `bug_fix_finance_wrong_compare` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: main.py.

TASK: The module `main.py` contains a software defect (invoice total computation). Find the bug and fix it IN PLACE in main.py (invoice parsing, subtotal, bulk discount, tax). Do not change the module's public API, do not add new dependencies, do not weaken behavior.
Files in the workdir are yours to edit.
Difficulty: medium (a ~50-line module with a seeded logic bug).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the fixed module passes all of the project's unit tests (run them if you can).
````

#### `bug_fix_scheduling_offbyone` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: main.py.

TASK: The module `main.py` contains a software defect (shift-scheduling logic). Find the bug and fix it IN PLACE in main.py (overlap detection, merging, hours). Do not change the module's public API, do not add new dependencies, do not weaken behavior.
Files in the workdir are yours to edit.
Difficulty: medium (a ~40-line module with a seeded logic bug).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the fixed module passes all of the project's unit tests (run them if you can).
````

#### `bug_fix_scheduling_wrong_compare` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: main.py.

TASK: The module `main.py` contains a software defect (shift-scheduling logic). Find the bug and fix it IN PLACE in main.py (overlap detection, merging, hours). Do not change the module's public API, do not add new dependencies, do not weaken behavior.
Files in the workdir are yours to edit.
Difficulty: medium (a ~40-line module with a seeded logic bug).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the fixed module passes all of the project's unit tests (run them if you can).
````

#### `bug_fix_scheduling_wrong_key` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: main.py.

TASK: The module `main.py` contains a software defect (shift-scheduling logic). Find the bug and fix it IN PLACE in main.py (overlap detection, merging, hours). Do not change the module's public API, do not add new dependencies, do not weaken behavior.
Files in the workdir are yours to edit.
Difficulty: medium (a ~40-line module with a seeded logic bug).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the fixed module passes all of the project's unit tests (run them if you can).
````

#### `bug_fix_text_offbyone` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: main.py.

TASK: The module `main.py` contains a software defect (text-processing helpers). Find the bug and fix it IN PLACE in main.py (slugify, word frequency, sentence splitting). Do not change the module's public API, do not add new dependencies, do not weaken behavior.
Files in the workdir are yours to edit.
Difficulty: medium (a ~40-line module with a seeded logic bug).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the fixed module passes all of the project's unit tests (run them if you can).
````

#### `bug_fix_text_wrong_compare` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: main.py.

TASK: The module `main.py` contains a software defect (text-processing helpers). Find the bug and fix it IN PLACE in main.py (slugify, word frequency, sentence splitting). Do not change the module's public API, do not add new dependencies, do not weaken behavior.
Files in the workdir are yours to edit.
Difficulty: medium (a ~40-line module with a seeded logic bug).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the fixed module passes all of the project's unit tests (run them if you can).
````

#### `bug_fix_text_wrong_regex` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: main.py.

TASK: The module `main.py` contains a software defect (text-processing helpers). Find the bug and fix it IN PLACE in main.py (slugify, word frequency, sentence splitting). Do not change the module's public API, do not add new dependencies, do not weaken behavior.
Files in the workdir are yours to edit.
Difficulty: medium (a ~40-line module with a seeded logic bug).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the fixed module passes all of the project's unit tests (run them if you can).
````

### implement_function (6 unique tasks)

#### `implement_edit_distance` — se_hard
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: solution.py.

TASK: Implement the function described in `solution.py` (Levenshtein edit distance). Replace the `raise NotImplementedError` body with a correct, efficient implementation in `solution.py`. Handle edge cases (empty inputs, boundaries). Do not change the signature. The project's hidden unit tests will be run against your file.
Difficulty: hard (non-trivial algorithm, edge cases).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: every hidden unit test passes.
````

#### `implement_flatten_json` — se_hard
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: solution.py.

TASK: Implement the function described in `solution.py` (flatten nested JSON objects). Replace the `raise NotImplementedError` body with a correct, efficient implementation in `solution.py`. Handle edge cases (empty inputs, boundaries). Do not change the signature. The project's hidden unit tests will be run against your file.
Difficulty: hard (non-trivial algorithm, edge cases).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: every hidden unit test passes.
````

#### `implement_knapsack` — se_hard
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: solution.py.

TASK: Implement the function described in `solution.py` (0/1 knapsack dynamic programming). Replace the `raise NotImplementedError` body with a correct, efficient implementation in `solution.py`. Handle edge cases (empty inputs, boundaries). Do not change the signature. The project's hidden unit tests will be run against your file.
Difficulty: hard (non-trivial algorithm, edge cases).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: every hidden unit test passes.
````

#### `implement_lru_cache` — se_hard
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: solution.py.

TASK: Implement the function described in `solution.py` (LRU cache with capacity). Replace the `raise NotImplementedError` body with a correct, efficient implementation in `solution.py`. Handle edge cases (empty inputs, boundaries). Do not change the signature. The project's hidden unit tests will be run against your file.
Difficulty: hard (non-trivial algorithm, edge cases).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: every hidden unit test passes.
````

#### `implement_max_profit` — se_hard
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: solution.py.

TASK: Implement the function described in `solution.py` (maximum profit from one buy and one sell). Replace the `raise NotImplementedError` body with a correct, efficient implementation in `solution.py`. Handle edge cases (empty inputs, boundaries). Do not change the signature. The project's hidden unit tests will be run against your file.
Difficulty: hard (non-trivial algorithm, edge cases).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: every hidden unit test passes.
````

#### `implement_merge_intervals` — se_hard
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: solution.py.

TASK: Implement the function described in `solution.py` (merge overlapping intervals). Replace the `raise NotImplementedError` body with a correct, efficient implementation in `solution.py`. Handle edge cases (empty inputs, boundaries). Do not change the signature. The project's hidden unit tests will be run against your file.
Difficulty: hard (non-trivial algorithm, edge cases).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: every hidden unit test passes.
````

### refactor (3 unique tasks)

#### `refactor_config` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: ugly.py.

TASK: Refactor `ugly.py` (config validator with global error buffer and duplicated checks). The code works but violates basic engineering standards: it relies on module-level global state and duplicate logic. Rewrite it as clean, well-structured code: split the logic into small focused functions with docstrings, use module-level constants instead of mutable globals, and remove all duplicated blocks. The public API (function names and signatures) must stay identical and the behavior must be preserved exactly.
Difficulty: medium-hard (structural refactor, behavior must not change).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: all hidden unit tests pass AND no global-state anti-patterns remain.
````

#### `refactor_invoice` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: ugly.py.

TASK: Refactor `ugly.py` (invoice formatter with global rate and duplicated block). The code works but violates basic engineering standards: it relies on module-level global state and duplicate logic. Rewrite it as clean, well-structured code: split the logic into small focused functions with docstrings, use module-level constants instead of mutable globals, and remove all duplicated blocks. The public API (function names and signatures) must stay identical and the behavior must be preserved exactly.
Difficulty: medium-hard (structural refactor, behavior must not change).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: all hidden unit tests pass AND no global-state anti-patterns remain.
````

#### `refactor_logs` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: ugly.py.

TASK: Refactor `ugly.py` (log summarizer with global counters and duplicated counting). The code works but violates basic engineering standards: it relies on module-level global state and duplicate logic. Rewrite it as clean, well-structured code: split the logic into small focused functions with docstrings, use module-level constants instead of mutable globals, and remove all duplicated blocks. The public API (function names and signatures) must stay identical and the behavior must be preserved exactly.
Difficulty: medium-hard (structural refactor, behavior must not change).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: all hidden unit tests pass AND no global-state anti-patterns remain.
````

### write_tests (5 unique tasks)

#### `write_tests_banking` — se_hard
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: good.py, buggy.py.

TASK: The project contains two versions of the same module: `good.py` (correct) and `buggy.py` (one deliberately seeded defect). Your job is to write a unit test suite that would catch the defect (transfer does not debit the sender). Requirements:
1. Every test must pass against the correct module.
2. At least one test must FAIL against the buggy module.
3. Use `import mod` to reach the module under test and write plain functions named `test_*` containing `assert` statements (no test framework needed). Cover edge cases, not just happy paths.
Difficulty: hard (test design; the bug is subtle).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Your test code must be the ONLY code block in your reply.
````

#### `write_tests_cart` — se_hard
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: good.py, buggy.py.

TASK: The project contains two versions of the same module: `good.py` (correct) and `buggy.py` (one deliberately seeded defect). Your job is to write a unit test suite that would catch the defect (promo codes apply a fixed amount instead of a percentage). Requirements:
1. Every test must pass against the correct module.
2. At least one test must FAIL against the buggy module.
3. Use `import mod` to reach the module under test and write plain functions named `test_*` containing `assert` statements (no test framework needed). Cover edge cases, not just happy paths.
Difficulty: hard (test design; the bug is subtle).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Your test code must be the ONLY code block in your reply.
````

#### `write_tests_stats` — se_hard
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: good.py, buggy.py.

TASK: The project contains two versions of the same module: `good.py` (correct) and `buggy.py` (one deliberately seeded defect). Your job is to write a unit test suite that would catch the defect (median mutates its input list). Requirements:
1. Every test must pass against the correct module.
2. At least one test must FAIL against the buggy module.
3. Use `import mod` to reach the module under test and write plain functions named `test_*` containing `assert` statements (no test framework needed). Cover edge cases, not just happy paths.
Difficulty: hard (test design; the bug is subtle).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Your test code must be the ONLY code block in your reply.
````

#### `write_tests_temperature` — se_hard
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: good.py, buggy.py.

TASK: The project contains two versions of the same module: `good.py` (correct) and `buggy.py` (one deliberately seeded defect). Your job is to write a unit test suite that would catch the defect (average truncates instead of rounding). Requirements:
1. Every test must pass against the correct module.
2. At least one test must FAIL against the buggy module.
3. Use `import mod` to reach the module under test and write plain functions named `test_*` containing `assert` statements (no test framework needed). Cover edge cases, not just happy paths.
Difficulty: hard (test design; the bug is subtle).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Your test code must be the ONLY code block in your reply.
````

#### `write_tests_urlparser` — se_hard
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: good.py, buggy.py.

TASK: The project contains two versions of the same module: `good.py` (correct) and `buggy.py` (one deliberately seeded defect). Your job is to write a unit test suite that would catch the defect (query values are returned as single strings instead of lists). Requirements:
1. Every test must pass against the correct module.
2. At least one test must FAIL against the buggy module.
3. Use `import mod` to reach the module under test and write plain functions named `test_*` containing `assert` statements (no test framework needed). Cover edge cases, not just happy paths.
Difficulty: hard (test design; the bug is subtle).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Your test code must be the ONLY code block in your reply.
````

### fastapi_setup (3 unique tasks)

#### `fastapi_catalog` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: README.md, data.json.

TASK: Build a small FastAPI application from the spec in `README.md` (item catalog API with search). Create `app.py` (and `requirements.txt` if needed) in the workdir. Follow the spec exactly: endpoints, status codes, error handling (404 for missing resources), and request/response shapes.
Difficulty: medium (multi-endpoint API with error handling).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: every endpoint from the spec exists with the documented behavior.
````

#### `fastapi_orders` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: README.md, data.json.

TASK: Build a small FastAPI application from the spec in `README.md` (order API that computes totals). Create `app.py` (and `requirements.txt` if needed) in the workdir. Follow the spec exactly: endpoints, status codes, error handling (404 for missing resources), and request/response shapes.
Difficulty: medium (multi-endpoint API with error handling).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: every endpoint from the spec exists with the documented behavior.
````

#### `fastapi_todos` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: README.md, data.json.

TASK: Build a small FastAPI application from the spec in `README.md` (todo list API). Create `app.py` (and `requirements.txt` if needed) in the workdir. Follow the spec exactly: endpoints, status codes, error handling (404 for missing resources), and request/response shapes.
Difficulty: medium (multi-endpoint API with error handling).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: every endpoint from the spec exists with the documented behavior.
````

### docker_configure (3 unique tasks)

#### `docker_cron_worker` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: worker.py, requirements.txt, README.md.

TASK: Containerize the project in the workdir (a scheduled worker script). Create a `Dockerfile` and a `docker-compose.yml` that follow current best practices (slim base image pinned to a major version, workdir set, dependencies installed from `requirements.txt`, non-default exposed port, healthcheck where reasonable). The compose service must build from the local Dockerfile, publish the app port, and mount the app as a volume.
Difficulty: medium (containerization conventions).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: a valid Dockerfile and compose file that would build and run the app.
````

#### `docker_flask_api` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: app.py, requirements.txt, README.md.

TASK: Containerize the project in the workdir (a Flask REST API). Create a `Dockerfile` and a `docker-compose.yml` that follow current best practices (slim base image pinned to a major version, workdir set, dependencies installed from `requirements.txt`, non-default exposed port, healthcheck where reasonable). The compose service must build from the local Dockerfile, publish the app port, and mount the app as a volume.
Difficulty: medium (containerization conventions).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: a valid Dockerfile and compose file that would build and run the app.
````

#### `docker_streamlit_dashboard` — se_medium
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: app.py, requirements.txt, README.md.

TASK: Containerize the project in the workdir (a Streamlit dashboard). Create a `Dockerfile` and a `docker-compose.yml` that follow current best practices (slim base image pinned to a major version, workdir set, dependencies installed from `requirements.txt`, non-default exposed port, healthcheck where reasonable). The compose service must build from the local Dockerfile, publish the app port, and mount the app as a volume.
Difficulty: medium (containerization conventions).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: a valid Dockerfile and compose file that would build and run the app.
````

### cli_tool (4 unique tasks)

#### `cli_filter` — se_complex
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: README.md, people.csv.

TASK: Build a small command-line tool from the spec in `README.md` (CSV filter CLI). Create `cli.py` in the workdir using argparse (flags exactly as documented in the spec). The tool must read the data file from the current directory and print output to stdout in the exact format shown in the spec.
Difficulty: complex (CLI contract must match exactly).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the grader runs your `cli.py` with documented arguments and compares stdout line-by-line.
````

#### `cli_json_pretty` — se_complex
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: README.md, config.json.

TASK: Build a small command-line tool from the spec in `README.md` (pretty-printing JSON CLI). Create `cli.py` in the workdir using argparse (flags exactly as documented in the spec). The tool must read the data file from the current directory and print output to stdout in the exact format shown in the spec.
Difficulty: complex (CLI contract must match exactly).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the grader runs your `cli.py` with documented arguments and compares stdout line-by-line.
````

#### `cli_sales` — se_complex
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: README.md, orders.csv.

TASK: Build a small command-line tool from the spec in `README.md` (sales summary CLI). Create `cli.py` in the workdir using argparse (flags exactly as documented in the spec). The tool must read the data file from the current directory and print output to stdout in the exact format shown in the spec.
Difficulty: complex (CLI contract must match exactly).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the grader runs your `cli.py` with documented arguments and compares stdout line-by-line.
````

#### `cli_word_freq` — se_complex
````text
You are a software engineer working on a real codebase. Be precise: write clean, working code and verify your own work before finishing.

Workdir files you may need: README.md, text.txt.

TASK: Build a small command-line tool from the spec in `README.md` (word frequency CLI). Create `cli.py` in the workdir using argparse (flags exactly as documented in the spec). The tool must read the data file from the current directory and print output to stdout in the exact format shown in the spec.
Difficulty: complex (CLI contract must match exactly).
Edit the files in the workdir using your file tools. When you provide code in your reply, wrap each file in a code fence named after the file path (e.g. ```python
# main.py
...
```).
Expected: the grader runs your `cli.py` with documented arguments and compares stdout line-by-line.
````

---

## Who decides right or wrong? — the deterministic grader (no AI)

**A plain Python program decides — never the model, never you.** Each task has a hidden test set (the `expected` column in the CSV, which the agent never sees), and the grader executes it:

- **bug_fix / implement / refactor** — the grader loads the agent's edited file as a module and runs 5–8 hidden assertions, e.g. `knapsack(10, [5,4,6,3], [10,40,30,50]) == 90`. Score = passed ÷ total.

- **write_tests** — runs the agent's tests in a subprocess against the *correct* module (must pass) and the *buggy* one (must catch the bug).

- **cli_tool** — actually executes `python cli.py --input ...` and compares stdout lines to the expected output.

- **fastapi / docker** — reads the produced files and checks the required elements are present.


Score ≥ 0.7 → **task passed**. The SE dataset contains zero `llm_judge` tasks, so no LLM is involved in grading: the same input always produces the same score.
