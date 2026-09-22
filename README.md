# UML viewer

A live architecture monitor that runs beside an AI coding agent. It draws
your module tree, paints dependency-rule violations red, colors boxes from
CRAP and mutation scores, and lets you click through to source. You tell
the agent what you don't like; the agent edits policy or code; the diagram
reloads.

One box is one module: a Clojure namespace, a Python file, or a TypeScript
file. Directories are the nesting. Classes and functions are members on
the card. A class in one module that extends or implements a type in
another module is an edge between those two modules.

## What you need

The window is a Java desktop app. Python and Node are used only to parse
those languages, and they live inside this tool checkout, not inside the
project you are viewing.

| Tool | Required for |
|------|----------------|
| Java 17+ | The viewer window |
| [Clojure CLI](https://clojure.org/guides/install_clojure) (`clj`) | Resolving the viewer the first time |
| Git | Cloning this tool |
| [Poetry](https://python-poetry.org/docs/#installation) | Scanning a Python project |
| Node.js and npm | Scanning a TypeScript project |
| tmux | Optional. Only the Grok companion uses it. The window opens without it |

Install Clojure on macOS with `brew install clojure`. Check the machine:

```bash
bin/uml doctor
```

## Install the command

Once, from this checkout:

```bash
bin/uml install
```

That links `uml` onto `~/.local/bin`. Open a new shell if that directory
is not already on `PATH`.

## Open a project

From the root of the repository you want to watch:

```bash
cd /path/to/your-project
uml
```

That is the whole flow. `uml` detects Python or TypeScript, writes
`uml-viewer.policy.edn` from the real directories, writes `uml-viewer.edn`,
and opens the window on the diagram. It does not invent layers. It does
not start a companion, and it does not wait for you to press **R**.

The first run downloads the viewer jars into this checkout (`.uml-home/`)
and installs the scanner for the language it finds. Later runs reuse that.

`uml` also adds a gitignore block for `.uml-viewer/`, `.metrics/`, and
`uml-viewer.edn`. Keep `uml-viewer.policy.edn`. That is the file you edit
when you want box order, a library drawn as an oval, or the dependency
rule. After you edit it, run `uml` again.

| Command | What it does |
|---------|----------------|
| `uml` | Scan, write the diagram, open the window |
| `uml refresh` | Scan and write the diagram |
| `uml show [file.edn]` | Open a diagram that already exists |
| `uml coverage <file>` | Import a coverage.py or Istanbul JSON report |
| `uml mutate <file>` | Import a mutmut, Stryker, or normalized mutation report |
| `uml doctor` | Check Java, Clojure, Poetry, Node, and the scanners |
| `uml install` | Link the command onto `~/.local/bin` |
| `uml help` | Print the command list |

Add `:levels` to the policy when you want inward dependencies to stay grey
and outward ones to turn red. Inner groups come first. Then run `uml` again.

### Python

Layout the scanner expects:

```text
your-project/
  src/myapp/domain/models.py
  src/myapp/app/loan.py
  uml-viewer.policy.edn    # written by uml
  uml-viewer.edn           # written by uml; gitignored
```

`src/myapp/domain/models.py` with prefix `myapp` becomes the module
`:domain.models`. `__init__.py` is the package module itself. If there is
no `src/` directory, discover scans the project root and sets `:src` to
`"."`. When every module shares a longer path, such as
`src/datateam/datamart/mcp/...`, that whole path is the prefix and the
first boxes are the directories under it.

A first policy looks like this:

```edn
{:title "myapp"
 :src "src"
 :prefix "myapp"
 :lang :python
 :out "uml-viewer.edn"
 :hierarchical true
 :foreign []
 :order [:domain :app]
 :omit []}
```

`:order` is box order, using directory names that already exist. To turn
on the red dependency rule, add `:levels` with the inner group first, then
regenerate:

```edn
:levels [[:domain] [:app]]
```

```bash
uml
```

A dependency from `:app`
to `:domain` is allowed. A dependency from `:domain` to `:app` is red.

The scanner skips `tests/`, `test/`, `*_test.py`, `test_*.py`,
`conftest.py`, virtualenvs, and build output. A module whose public
surface is only `Protocol` or `ABC` classes is an interface. Subclassing
one of those in another module is an implements edge. Subclassing a
concrete class is inheritance. Names that start with `_` are private:
they stay off the box and show with a minus on the class card.

### TypeScript

```text
your-project/
  tsconfig.json
  src/domain/book.ts
  src/app/loan.ts
  src/app/index.ts
```

One `.ts` or `.tsx` file is one module. `src/app/index.ts` is the `:app`
module. `src/domain/book.ts` is `:domain.book`. The prefix stays empty.
`tsconfig.json` `baseUrl` and `paths` are honored, so `@domain/book`
resolves to the project file. A bare package import (`react`, `zod`) is
foreign and is dropped unless you name it in `:foreign`.

`import type` counts. The dependency rule is about source dependencies,
and a type import is source.

A file that only exports `interface` or `type` is an interface. A file
that only exports an `abstract class` is abstract. A file that only
exports an `enum` is an enumeration. `implements` and `extends` across
files become implements and inheritance edges.

The scanner skips `node_modules`, `dist`, `*.test.ts`, `*.spec.ts`,
`*.d.ts`, and `__tests__/`.

Discover writes a policy with `:lang :typescript` and `:prefix ""`. Add
`:levels` the same way as Python when you want red arrows, then run `uml`.

### A second package

A monorepo is one diagram per package. `cd` into the package that has its
own `src/` (and its own `tsconfig.json`, for TypeScript) and run `uml`
there.

## Day to day

Run `uml` again after the tree changes. It re-reads the directories, keeps
`:levels` and `:proposals` you already wrote, regenerates `uml-viewer.edn`
and `.metrics/crap.edn`, and opens the window. Do not hand-edit
`uml-viewer.edn`.

An open window reloads when the EDN or `.metrics/` changes. **R** reloads
immediately.

`./uml` from an older per-project install still starts the companion and
waits for `:display`. Prefer the `uml` command above. `--restart` is only
for that companion recycling its own window.

## Coverage and mutation

Missing scores paint red. The static scan fills cyclomatic complexity and
leaves coverage empty, so boxes start red until a coverage file is
imported. A later scan keeps coverage for members that still exist.

CRAP is `CC² * (1 - cov)³ + CC`.

### Python

From the project you are viewing, with that project's own environment:

```bash
poetry run coverage run -m pytest
poetry run coverage json -o coverage.json
uml coverage coverage.json
```

Any `coverage.py` JSON report works. The command joins executed and missing
lines to each function's line range.

Mutation runs the project's tests, so it uses the project's environment
too. mutmut writes a SQLite cache; pass that file:

```bash
poetry run mutmut run
uml mutate .mutmut-cache
```

A [Stryker](https://stryker-mutator.io/) JSON report works for Python as
well. Pass the report path you actually got.

### TypeScript

```bash
npx c8 --reporter json npm test
uml coverage coverage/coverage-final.json
```

Istanbul `coverage-final.json` is the same shape. Point `uml coverage`
at the file your runner wrote.

```bash
npx stryker run
uml mutate reports/mutation-report.json
```

If Stryker writes the JSON somewhere else, pass that path. A normalized
report is also accepted: `{"modules":[{"namespace":"app.loan","source":"src/app/loan.py","forms":[{"name":"issue","private":false,"killed":1,"survived":0,"uncovered":0,"sites":1}]}]}`.

## Working with an agent

The viewer writes a queue to `.uml-viewer/to-agent.edn`. The agent pops
that queue, edits policy or code, regenerates, and can tell the viewer
which file to show. Nothing in the viewer starts Cursor. You talk to the
agent you already have.

`uml` writes two instruction files for Python and TypeScript.
`.uml-viewer/AGENT.md` is what a Cursor agent should read.
`.grok/rules/uml-viewer.md` is the same text, and the Grok CLI loads
every markdown file in that directory on its own.

`bin/uml install` also links a user skill at `~/.grok/skills/uml-viewer`.
In a repo that does not have the viewer yet, start Grok and ask it to
install or open the diagram, or run `/uml-viewer`. The skill runs `uml`
when the command is already on `PATH`, and `bin/uml install` when you are
in the tool checkout and the command is missing. It does not clone the
tool into the project. After the first `uml`, Grok follows
`.grok/rules/uml-viewer.md` in that repo without the skill.

A short version of what the agent is supposed to do:

1. On the first turn, run `uml refresh` if the diagram is missing. Do not
   invent packages. Do not invent `:proposals`.
2. When you set architectural rank, the agent adds `:levels` to the policy
   and runs `uml refresh`. Inner (higher-level) groups come first.
3. After code or policy changes, `uml refresh`. Refresh coverage with the
   project's test command and `uml coverage`. Mutation is optional.
4. Pop each mailbox command after handling it. Do not overwrite the file.

Right-click a box for **Refresh CRAP**, **Refresh Mutation**, **Refresh
All Mutation**, or **Omit**. **Regen** in the inspector queues a full
regenerate. Those buttons write the mailbox; they do not run the tests
themselves. The agent does.

Grok in tmux is still started by `./uml` when `grok` is on the path
(`GROK_BIN`, `~/.grok/bin/grok`, `/usr/local/bin/grok`, or
`/opt/homebrew/bin/grok`). The session name is
`uml-viewer-<project>-<hash>`, stored in `.uml-viewer/companion.edn`.
Closing the diagram kills only that session. `--restart` is for that
companion recycling the window after it writes `:quit-for-restart`. A
stray `--restart` skips spawning a companion. Do not SIGKILL the window.

## Navigation

**Layer** and **component** mean the same thing: a grouping of modules
(the first segment after the prefix, or a named proposal group).

- First view: those components. Dependencies between them collapse to one
  arrow. Each component lists the modules inside it.
- Double-click a component to open the next level. Esc or the ← label goes
  up a level. Esc does not quit. The window close box exits the app.
- Hover an arrow for every `from -> to` it bundles. Violating pairs are red.
- Right-click a module or component for the mailbox actions above.
- The inspector lists the **real diagram** above **Proposals**. Click the
  real row to return to the tree; click a proposal to show a grouping that
  is not in the source (the canvas says it is not instantiated). **New
  Proposal** adds a timestamp-named proposal. Right-click to rename or
  delete.
- **Declutter** cycles Declutter arrows / Remove arrows / Declutter
  elements / Declutter classes / Declutter none. **Remove arrows** hides
  the lines and puts a triangle on the top (incoming) and bottom
  (outgoing) of each box. A triangle is red if any bundled pair is
  violating.
- Double-click a leaf module for its **class card**.
- The class card names the module. Click the name to open that file at
  the top. Click a member to open the same file on that function.
- Methods on the card are `+` public and `-` private. Private members are
  not drawn on the box.
- Abstract classes show a white **α** in the upper-right; interfaces a
  white **I**. Foreign libraries listed in `:foreign` are ovals.
- The main window is resizable.
- Scroll to pan vertically; Shift-scroll (or left/right arrows) for
  horizontal.
- **Ctrl+** (or **Ctrl+=**) zooms in 10%; **Ctrl-** zooms out 10%;
  **Ctrl+0** restores 100%.
- **R** reloads the current EDN. After the first reload, saving the EDN
  or anything under `.metrics/` reloads on its own. An open class card
  updates with the new numbers.

## Policy

The diagram is generated. Edit the policy, then `uml`.

| Key | Role |
|-----|------|
| `:lang` | `:python`, `:typescript`, or `:clojure` |
| `:src` | Source root, usually `"src"` |
| `:prefix` | Strip this from each module id. Remaining dots are the tree. Empty for TypeScript |
| `:out` | Where `uml` writes the diagram. Discover uses `uml-viewer.edn` |
| `:hierarchical` | Module tree (this is the normal mode) |
| `:order` | Order of **existing** top-level directories, not new component names |
| `:levels` | Groups of those directories, **inner (higher-level) first**. Same group = same rank. Omit it and nothing is marked red |
| `:foreign` | Libraries drawn as ovals. Anything else imported from outside the project is dropped |
| `:proposals` | Named groupings of real directories. Not created in the source tree |
| `:omit` | Modules (and their children) left off the diagram |
| `:edge-kinds` | Override an edge, usually `{[:from :to] :association}` using leaf ids |
| `:omit-edges` | Drop `[from to]` |

Python example once you care about rank:

```edn
{:title "myapp"
 :src "src"
 :prefix "myapp"
 :lang :python
 :out "uml-viewer.edn"
 :hierarchical true
 :foreign []
 :order [:domain :app]
 :levels [[:domain] [:app]]}
```

TypeScript is the same with `:lang :typescript` and `:prefix ""`.
`src/domain/book.ts` is `:domain.book`.

Wrong (invented partitions the scanner will not create in the tree):

```edn
:packages [{:id :domain :nses [models]}
           {:id :app :nses [loan]}]
```

To **view** a grouping that is not in the code, use `:proposals`. To **make**
Domain and App boxes, those directories have to exist.

### Dependency rule

A `:dependency` edge is **violating** when it runs from a higher-level
(inner) component to a lower-level (outer) one.

1. Take the first dotted segment of each end (`domain.models` → `domain`).
2. Look up that segment in `:levels`. Rank is the group's index; smaller
   is inner.
3. If both ends have a rank and the source is inner relative to the
   target, the edge is violating. Same rank is allowed. Implements and
   inheritance are never violating.
4. A collapsed component arrow stays red if any bundled leaf dependency
   was violating.

`:order` is visual box order, not rank. Omit `:levels` and nothing is
marked. If `:levels` is omitted and `:proposals` is set, rank follows the
first proposal's component order while that proposal is on screen.

### Proposed components

`:proposals` groups existing top-level directories under names that are
not modules. The as-is diagram stays the tree. The canvas marks a proposal
**PROPOSAL — not instantiated in code**.

```edn
:proposals [{:id :ccp
             :name "2026-09-18 10:30:00"
             :layers [{:id :playfield :label "Playfield"
                       :nses [:domain :app]}]}]
```

The agent must not invent `:proposals` on its own and must keep them when
it rewrites `:order`.

## Companion mailbox

Files live in `.uml-viewer/` in the project you are viewing (gitignored).

| File | Direction |
|------|-----------|
| `.uml-viewer/to-agent.edn` | viewer → agent |
| `.uml-viewer/to-viewer.edn` | agent → viewer |
| `.uml-viewer/AGENT.md` | standing instructions for a Python or TypeScript companion |
| `.uml-viewer/session.edn` | last depth, pan, zoom, and proposal; restored by `--restart` |
| `.uml-viewer/companion.edn` | tmux session and Terminal window for the Grok companion |

Each mailbox file is `{:next-id n :queue [cmd …]}`. Append; do not
overwrite. Handling a command pops it from `:queue`. The viewer pops
`to-viewer.edn` itself. The agent must pop `to-agent.edn`.

| `:op` | Meaning |
|-------|---------|
| `:display` | Viewer loads `:path` (relative to the project root) and leaves the waiting screen |
| `:regen` | Agent rewrites the policy tree, runs `./uml ir`, then `:display` |
| `:quit-for-restart` | Viewer exits. The companion then runs `./uml --restart` |
| `:refresh-crap` | Agent reruns coverage for `:target`, then `./uml coverage` and `./uml ir` |
| `:refresh-mutate` | Agent runs mutation for `:target`, then `./uml mutate` |
| `:refresh-mutate-all` | Same, across the files under that component |
| `:omit` | Add `:target`'s id to the current proposal's `:omit`, or to policy `:omit` on the real diagram, then regenerate |
| `:context` | `{:context :real}` or `{:context :proposal :proposal-id id :name "…"}` |

`:target` is `{:id :ns :kind :class|:component :proposal-id?}`. `:kind` is
`:component` for a layer box and `:class` for a module.

To show a diagram without pressing **R**, the agent appends a `:display`
command whose `:path` is `uml-viewer.edn`.

## Language graphs

`:lang` selects the scanner.

| Language | What one box is | Edges |
|----------|-----------------|-------|
| `:python` | A `.py` file. `__init__.py` is the package | Imports, including relative imports and a literal `importlib.import_module("...")`. Implements when the base is a project `Protocol` or `ABC`; inheritance when the base is a concrete class |
| `:typescript` | A `.ts` or `.tsx` file. `index.ts` is the directory | Relative imports, `tsconfig` path aliases, `import type`, and dynamic `import()`. `implements` and `extends` across files |
| `:clojure` | A namespace | `:require`, `:use`, and `requiring-resolve` of a quoted var. `defprotocol` is an interface. `defrecord` / `deftype` of a protocol is implements |

Both external scanners emit the same facts the Clojure scanner emits:
classes `{:id :name :ns :stereotype :foreign}` and edges
`{:from :to :kind}` with kind `:dependency`, `:implements`, or
`:inheritance`. Policy then drops unlisted foreign modules, applies
`:levels`, and builds proposals. Agents edit the policy, not the IR.

Register another language with `(graph/register! :java my-java-scanner)`
and `(source/register! :java my-java-extractor)`. Do not special-case a
language inside policy.

## From this repository

Use this when you are changing the viewer itself.

```bash
poetry -C analyzers/python install
npm --prefix analyzers/typescript install
clj -M:ir          # examples/uml-viewer.policy.edn → examples/uml-viewer.edn
clj -M:run examples/uml-viewer.edn
clj -M:spec
```

Press **R** after the window opens. `clj -M:discover` writes a policy for
a Python or TypeScript tree (this repo's own policy stays the Clojure
one under `examples/`). `clj -M:crap` and `clj -M:mutate` are the Clojure
metric tools and are not used for Python or TypeScript.

## IR

A hierarchical policy writes one EDN document. The viewer builds each
screen from the module tree at the current drill level. Hand-written
diagrams such as `examples/library.edn` still load.

The generator stores `:lang` and `:src` on the document. Click-to-source
uses those. Members on the card come from `.metrics/crap.edn` and
`.metrics/mutate/**/*.edn`, joined on namespace plus function name.
Rename a function and it is a new row; old scores do not follow it.

Color maps CRAP and mutation onto a red–green fill. Missing data counts
as red. A **C** and **M** dot in the upper-right show the two scores.
Parents take the worst of their children.

Edge `:kind` values:

| kind | line | head |
|------|------|------|
| `:inheritance` | solid grey | empty triangle |
| `:implements` | solid grey | empty triangle |
| `:association` | solid grey | open arrow |
| `:dependency` | solid grey | open arrow |
| `:aggregation` | solid grey | empty diamond |
| `:composition` | solid grey | filled diamond |

Violating dependencies are red, and bold red when a selected element
highlights them.

## Source

Clicking a member opens the whole file and scrolls to that line. Clicking
the module name opens the same file at the top. `:lang` on the open
document selects the extractor: Clojure maps a namespace to `src/...clj`
and finds a top-level `defn`; Python and TypeScript use the file and line
the scanner recorded.
