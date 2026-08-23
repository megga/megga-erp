---
name: refactor
description: Systematically analyze and refactor code to improve quality without changing behavior. Use when asked to refactor, clean up, or restructure code in a file or directory — /refactor [path].
---

# Code Refactor Skill

Systematically analyze and refactor code to improve quality without changing behavior.

<!-- Source: https://www.claudedirectory.org/skills/refactor (Claude Code Community) — reviewed and imported 2026-08-23 -->

## Usage
```
/refactor [file or directory path]
```

## Behavior
1. Analyze the target code for refactoring opportunities
2. Identify code smells, duplication, and complexity issues
3. Propose specific refactoring steps with rationale
4. Apply refactorings incrementally, verifying tests pass after each step

## Refactoring Categories

### Structure
- Extract function/method for repeated logic
- Extract component for reusable UI patterns
- Move code closer to where it's used
- Split large files by responsibility

### Simplification
- Replace complex conditionals with guard clauses
- Simplify nested callbacks with async/await
- Replace magic numbers with named constants
- Remove dead code and unused imports

### Patterns
- Replace inheritance with composition
- Apply strategy pattern for variant behavior
- Use builder pattern for complex object construction
- Introduce early returns to reduce nesting

## Safety Guarantees
- Never changes external behavior
- Runs existing tests after each refactoring step
- Creates atomic commits for each logical change
- Preserves all public API signatures unless explicitly requested

## Project rule (Odoo overlay)
In this project, refactoring applies ONLY to our own modules (addons/) and scripts.
The `odoo/` submodule is upstream code, mounted read-only: it is never a refactoring
target, whatever its code smells. See PLAN-REPRISE-ODOO.md.

## Example
```
/refactor src/utils/parser.ts
```
Analyzes parser.ts and applies targeted refactorings with test verification at each step.
