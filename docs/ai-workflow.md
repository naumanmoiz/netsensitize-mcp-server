# AI Development Workflow

## Roles

Claude:
- Primary code generator
- Produces production-ready modules

Opencode:
- Security validator
- Refactor engine
- Performance reviewer

CodeRabbit:
- Final PR review
- Pattern enforcement
- Quality gate

---

## Workflow

1. Draft requirement
2. Send to Claude
3. Receive implementation
4. Send to Opencode
5. Apply fixes
6. Push to GitHub
7. CodeRabbit PR review
8. Merge

---

## Rules

- Claude does not validate security
- Opencode does not redesign architecture
- CodeRabbit does not rewrite major logic

---

## Logging

All AI sessions:
- Saved under logs/
- Tagged with version
- Linked to commit ID