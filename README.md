# Codex Workflow Toolkit

> A personal collection of Skills, MCP servers, tools, prompts, and workflow automation built to make Codex more useful in real daily work.

This repository is where I build and maintain the tools I use to extend **Codex** beyond a normal coding assistant.

The goal is simple:

**Turn repetitive workflows into reusable tools that Codex can understand, execute, and combine.**

Instead of repeatedly explaining the same process to an agent, I want to encode that process once as a Skill, MCP server, script, or workflow and reuse it whenever needed.

This repository is primarily built for my own daily workflow, but the components are intended to remain understandable, modular, and reusable by others.

---

## Why this repository exists

AI coding agents are powerful, but a large part of real work still involves repeatedly teaching them things such as:

- how a project should be audited;
- how local repositories should be inspected;
- which tests should be run;
- how reports should be generated;
- how Git changes should be reviewed;
- how external tools should be called;
- how browsers or desktop applications should be controlled;
- how project-specific workflows should be executed;
- and what steps should happen after an agent completes a task.

Most of these instructions should not have to be rewritten every time.

This repository turns those repeated instructions into reusable components.

The long-term idea is to build a personal **workflow layer around Codex**.

---

## What belongs here

The repository may contain several types of Codex extensions.

### Skills

Reusable instructions that teach Codex how to perform a specific workflow.

Examples:

```text
skills/
├── repository-audit/
├── release-review/
├── production-check/
├── benchmark-analysis/
└── test-runner/
```

A Skill should describe not only *what* Codex needs to do, but also:

- when it should be used;
- what information it should inspect;
- which operations are allowed;
- which operations are forbidden;
- how results should be verified;
- what the final report should contain.

The objective is to make complex workflows repeatable instead of relying on one-off prompts.

---

### MCP Servers

Custom **Model Context Protocol (MCP)** integrations that give Codex access to tools or environments that are not available by default.

Possible use cases include:

```text
mcp/
├── local-workspace/
├── workflow-runner/
├── browser-bridge/
├── git-tools/
└── custom-services/
```

An MCP server may expose capabilities such as:

- filesystem inspection;
- Git status and diff analysis;
- command execution;
- testing;
- build tools;
- repository metadata;
- browser automation;
- local applications;
- internal APIs;
- custom workflow services.

Whenever possible, MCP tools should expose small, explicit operations instead of giving the agent an unnecessarily broad interface.

---

### Workflow utilities

Some tasks do not require a full MCP server.

Small scripts and helpers may live under:

```text
scripts/
```

Examples include:

- environment setup;
- installing Skills;
- validating Skill structure;
- MCP configuration;
- launching local services;
- collecting diagnostics;
- running repeatable test suites;
- generating reports.

---

### Documentation

More complex tools should have their own documentation.

```text
docs/
├── architecture/
├── setup/
├── workflows/
└── troubleshooting/
```

Documentation should explain why a tool exists, not just how to run it.

---

## Proposed repository structure

As the project grows, the repository is expected to follow a structure similar to:

```text
The-skill-for-workflow-with-codex/
│
├── skills/
│   ├── repository-audit/
│   │   ├── SKILL.md
│   │   └── ...
│   │
│   ├── production-review/
│   │   ├── SKILL.md
│   │   └── ...
│   │
│   └── ...
│
├── mcp/
│   ├── local-workspace/
│   ├── git-tools/
│   └── ...
│
├── scripts/
│   ├── install/
│   ├── setup/
│   └── diagnostics/
│
├── examples/
│   ├── prompts/
│   ├── configs/
│   └── workflows/
│
├── docs/
│   ├── architecture/
│   ├── setup/
│   └── troubleshooting/
│
└── README.md
```

The exact structure may evolve as the toolkit grows.

---

## Design principles

### 1. Automate repeated instructions

If I have to explain the same procedure to Codex several times, that procedure is probably a candidate for a Skill or tool.

---

### 2. Agents should verify their work

A workflow should not end with:

```text
I changed the code.
```

It should end with evidence.

Depending on the task, this can include:

```text
git status
git diff
tests
build results
lint results
runtime checks
benchmark results
generated artifacts
```

A workflow should clearly distinguish between:

```text
implemented
tested
verified
production-ready
```

These are not the same thing.

---

### 3. Prefer deterministic tools over giant prompts

Prompts are useful for reasoning.

Tools are better for deterministic operations.

For example:

```text
Bad:

"Run some commands and inspect the repository."

Better:

git_status()
git_diff()
read_file()
run_tests()
project_context()
```

Codex should reason about **which tool to use** instead of spending tokens reconstructing basic operations.

---

### 4. Keep tools composable

A tool should ideally perform one clear operation.

Small operations are easier for an agent to:

- understand;
- combine;
- verify;
- retry;
- audit;
- secure.

---

### 5. Read before writing

For repository work, the default workflow should be:

```text
inspect
   ↓
understand
   ↓
plan
   ↓
modify
   ↓
test
   ↓
review diff
   ↓
report
```

Editing code before understanding the project is discouraged.

---

### 6. Never hide uncertainty

If an agent cannot verify something, the report should say so.

For example:

```text
NOT VERIFIED
```

is better than:

```text
Everything should probably work.
```

---

## Typical workflow

A Skill in this repository may orchestrate a workflow such as:

```text
User request
     │
     ▼
Codex Skill
     │
     ├── Read project context
     │
     ├── Inspect documentation
     │
     ├── Inspect Git state
     │
     ├── Analyze relevant code
     │
     ▼
Create implementation plan
     │
     ▼
Modify code
     │
     ▼
Run targeted tests
     │
     ▼
Run broader verification
     │
     ▼
Inspect Git diff
     │
     ▼
Generate final report
```

MCP servers provide the operations.

Skills provide the workflow and reasoning rules.

Codex coordinates both.

---

## Example Skill idea

A repository audit Skill might instruct Codex to:

```text
1. Determine repository root.
2. Read the core project documentation.
3. Inspect current branch and HEAD.
4. Inspect Git status.
5. Inspect working-tree changes.
6. Identify the subsystem relevant to the request.
7. Trace dependencies.
8. Look for correctness, architecture, concurrency,
   security, performance, and maintainability issues.
9. Separate confirmed problems from hypotheses.
10. Run targeted verification.
11. Produce a structured audit report.
```

Instead of writing this prompt repeatedly, the workflow can live permanently in the repository.

---

## Example MCP idea

A local development MCP could expose tools such as:

```text
project_context
read_text_file
search_code
git_status
git_diff
git_log
run_command
run_tests
```

Codex could then combine those primitives with higher-level Skills.

Conceptually:

```text
                 ┌──────────────────┐
                 │      Codex       │
                 └────────┬─────────┘
                          │
                  reasoning / planning
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
         ┌─────────┐             ┌─────────┐
         │ Skills  │             │   MCP   │
         └────┬────┘             └────┬────┘
              │                       │
        workflow logic           real tools
              │                       │
              └───────────┬───────────┘
                          ▼
                  local environment
```

---

## Adding a new Skill

A new Skill should ideally answer five questions:

```text
WHEN should this Skill be used?

WHAT problem does it solve?

WHAT tools may it use?

WHAT steps must it follow?

WHAT evidence proves completion?
```

Suggested layout:

```text
skills/my-skill/
├── SKILL.md
├── references/
├── templates/
└── scripts/
```

Avoid putting large amounts of unrelated knowledge directly into a single Skill.

Keep the core workflow concise and move supporting material into references when appropriate.

---

## Adding a new MCP server

Each MCP integration should document:

```text
Purpose
Requirements
Installation
Configuration
Available tools
Permissions
Security considerations
Example usage
Troubleshooting
```

A server should request only the permissions required for its intended workflow.

---

## Security

MCP servers can provide an AI agent with powerful access to the local machine.

Treat them as real software with real permissions.

Extra care should be taken with tools that can:

```text
execute shell commands
write files
delete files
modify Git repositories
access credentials
control browsers
access authenticated services
install software
modify system configuration
```

Where practical, tools should support a read-only mode.

Potentially destructive operations should be explicit and easy to distinguish from inspection operations.

Credentials, tokens, API keys, cookies, and private configuration must never be committed to this repository.

---

## Development philosophy

This repository is intentionally **workflow-driven**.

I am not trying to collect hundreds of random prompts.

The goal is to collect tools that remove friction from real work.

A useful addition should ideally satisfy at least one of these conditions:

- I use the workflow repeatedly.
- It removes repetitive manual steps.
- It improves the reliability of Codex.
- It gives Codex access to information it could not otherwise obtain.
- It provides stronger verification.
- It reduces the amount of context I need to explain manually.
- It makes an existing workflow safer or faster.

---

## Roadmap

The project is currently under active development.

Planned areas include:

- reusable Codex Skills;
- local repository inspection;
- Git-aware workflows;
- automated code auditing;
- test orchestration;
- production-readiness checks;
- browser-assisted workflows;
- custom MCP integrations;
- environment setup automation;
- reusable agent prompts;
- workflow reporting;
- multi-agent and sub-agent workflows.

The roadmap will evolve based on what proves useful in real daily work.

---

## Status

This is currently a **personal workflow repository** and is expected to change frequently.

APIs, folder structures, Skills, MCP interfaces, and setup procedures may evolve as the workflow becomes more mature.

Use individual components according to their own documentation.

---

## Contributions

The repository is primarily designed around my own Codex workflow, but ideas, bug reports, improvements, and reusable workflow patterns are welcome.

When proposing a new component, explain the real workflow problem it solves rather than only describing the implementation.

---

## Core idea

The simplest way to describe this project is:

```text
Things I repeatedly teach Codex
            ↓
        become Skills

Things Codex needs to interact with
            ↓
        become MCP tools

Things that should happen automatically
            ↓
        become workflows
```

Over time, the repository becomes a reusable operating layer for my daily work with Codex.

---

**Build the workflow once. Reuse it with Codex every day.**
