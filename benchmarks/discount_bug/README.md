# Percentage calculation
`apply_discount(100, 20)` should return 80. The intentional bug treats 20 as a fraction.
Known expected fix: replace `price * (1 - percent)` with `price * (1 - percent / 100)`.
The zero-discount test guards existing behavior. Run through DevPilot's Docker sandbox.
