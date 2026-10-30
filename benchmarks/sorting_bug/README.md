# Ascending sort
`ascending` must return values in ascending order without mutating its input.
Known expected fix: replace `sorted(values, reverse=True)` with `sorted(values)`.
The empty-list test guards existing behavior. Run through DevPilot's Docker sandbox.
