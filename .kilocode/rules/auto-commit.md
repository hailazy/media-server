# Auto-Commit Rule

When a task is completed successfully, you MUST automatically commit the changes using the following convention:

Format: `<type>(<scope>): <description>`

Types:
- feat: A new feature
- fix: A bug fix
- docs: Documentation only changes
- style: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- refactor: A code change that neither fixes a bug nor adds a feature
- perf: A code change that improves performance
- test: Adding missing tests or correcting existing tests
- chore: Changes to the build process or auxiliary tools and libraries such as documentation generation

Example: `feat(auth): add login validation`

**Procedure:**
1. Verify all tests pass (if applicable).
2. Stage all changed files: `git add .`
3. Commit with a descriptive message: `git commit -m "type(scope): description"`
4. If the commit fails due to hooks, fix the issues and retry.
