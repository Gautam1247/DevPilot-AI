# Inclusive boundary
`inclusive_numbers(3)` should include 3. The range stops one element too early.
Known expected fix: replace `range(1, n)` with `range(1, n + 1)`.
The empty-range case guards existing behavior. Run through DevPilot's Docker sandbox.
