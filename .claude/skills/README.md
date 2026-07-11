# Skills

This project's growing playbook of "how we do X here." Create a skill as soon as a pattern repeats — don't wait for a third occurrence, and don't pre-author one before the pattern actually exists.

Each skill is a folder with a `SKILL.md`:

```
.claude/skills/<skill-name>/SKILL.md
```

```markdown
---
name: <skill-name>
description: <one line, specific enough that it's obvious when this applies>
---

<concise body — steps, conventions, gotchas for this repeatable task>
```

Keep skill bodies out of `CLAUDE.md` — they load on demand when relevant, `CLAUDE.md` is always-on and should stay lean. Expect skills like "how we add a backend endpoint," "how we wire a new frontend view to the API," "how we structure and run tests," or "how we containerize and run the app" to appear here once those patterns exist.

No skills yet — none of the underlying patterns exist. Add the first one when a task repeats.
