---
title: Clean Code — Rules That Survive Reality
description: Fifteen opinionated rules a senior engineer actually applies in code review.
---

## The fifteen

| # | Rule | Why it survives |
|---|---|---|
| 1 | Functions do one thing, fit on a screen | If you can't name it without "and", it's two functions |
| 2 | Names reveal intent, not type | `users` not `userList`; `cancelOrder` not `process` |
| 3 | Boolean params are a code smell | Two methods beat `setEnabled(true/false)` every time |
| 4 | Command-Query Separation | Methods either *do* something or *answer* something — not both |
| 5 | Handle errors at boundaries, not everywhere | The transport layer catches, the domain throws |
| 6 | Prefer composition over inheritance | Inheritance is a coupling contract you sign forever |
| 7 | Don't abstract until the third repeat | Two duplicates are coincidence; three are a pattern |
| 8 | Log at the right level, with structure | `INFO` = lifecycle, `WARN` = recovered, `ERROR` = paged |
| 9 | Tests assert behavior, not implementation | If a refactor breaks tests, your tests test the wrong thing |
| 10 | Test the boundaries — not just the happy path | Empty, one, many, max, null, negative, concurrent |
| 11 | Small classes, single reason to change | If two stakeholders request changes here, split it |
| 12 | Make illegal states unrepresentable | Types over runtime checks; `Optional`, sealed types, value objects |
| 13 | Mutable shared state is the enemy | Confine it, immutate it, or guard it — pick one |
| 14 | Comments explain *why*, never *what* | If the code can't say what, the code is wrong, not the comment |
| 15 | Delete code aggressively | Dead code rots; the VCS remembers if you ever needed it |

## The smells (one example each)

**1. Long function** — A 200-line `processOrder` that validates, saves, charges, and emails. Split into four named steps you can test independently.

**2. Bad name** — `data`, `info`, `manager`, `helper`, `util`. These tell you nothing. `pendingOrders`, `priceCalculator`, `retryPolicy` do.

**3. Boolean param** — `repository.find(id, true)` — what is `true`? Replace with `findIncludingDeleted(id)`.

**4. CQS violation** — `User getUser(id)` that lazy-creates the user as a side effect. Now `getUser` mutates state, and you can't call it from a read-only context.

**5. Error at the wrong layer** — Catching `SQLException` in business logic and logging it. The repository should translate to a domain exception; the controller decides the HTTP code.

**6. Inheritance trap** — `class AdminUser extends User`. Then `User` adds a field admins shouldn't have. You're stuck.

**7. Premature abstraction** — Every service hidden behind an interface "in case we swap implementations". You won't. Add the interface when there are two.

**8. Wrong log level** — `log.info("validation failed: {}", err)` on every bad request. Now real INFO drowns in noise. That's a `DEBUG` or a counter.

**9. Implementation-coupled test** — `verify(repo).save(...)` for every test. Refactor the repo and 80 tests break — none of them tested behavior.

**10. Missing boundary** — `divide(a, b)` tested only with `(10, 2)`. Ship it; production hits `divide(10, 0)` on day one.

**11. Big class** — `OrderService` that knows about pricing, inventory, and email. Three reasons to change → three classes.

**12. Stringly-typed** — `enum Status { OPEN, CLOSED }` — but `String status` in the API. Now any typo is a runtime bug.

**13. Shared mutable** — `static Map<String, Cache>` updated from multiple threads without `Concurrent*` or a lock. Works in dev, races in prod.

**14. Wrong-comment** — `// increment by 1` above `i++`. Versus `// retry once because the upstream is flaky during failover`.

**15. Just-in-case code** — A flag that hasn't been flipped in two years. Delete it. If it's needed, the test suite will tell you.

## Reviewer's mantras

- "Can a new hire understand this in 60 seconds?"
- "What would I delete if I had to ship it tomorrow?"
- "Where does this break if traffic 10×'s?"
- "If this throws, what's the user-facing message?"
